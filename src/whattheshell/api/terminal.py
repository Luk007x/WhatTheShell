# SPDX-License-Identifier: AGPL-3.0-or-later
"""Interactive terminal steps: runner-side provider, PTY WebSocket, transcripts (SECURITY.md 7).

Keystrokes go from the WebSocket straight to the PTY; they are never logged, published or
written to a transcript. The path lies under ``/ws/``, so `SecurityMiddleware` checks
token, Host and Origin before this code runs.
"""

import asyncio
import codecs
import contextlib
import logging
import os
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Literal

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import Field, TypeAdapter, ValidationError

from whattheshell import paths
from whattheshell.api.errors import error_response
from whattheshell.engine import TerminalRequest, mask_text
from whattheshell.engine.runner import _MAX_TIMEOUT
from whattheshell.models.common import StrictModel
from whattheshell.sandbox import self_test
from whattheshell.terminal import PtyProcess, TerminalUnavailable, spawn

logger = logging.getLogger(__name__)

MAX_TERMINALS = 4  # as MAX_RUNNING_RUNS (api/runs.py)
IDLE_TIMEOUT = 15 * 60.0
MAX_CHUNK = 65536
MAX_BACKLOG = 1_048_576
_TICK = 0.1
_TRANSCRIPT_NAME = re.compile(r"^[A-Za-z0-9._-]+\.txt$")
_LINE_CAP = 65536  # a line without newline (progress bars) is flushed at this size

_REFUSED = {
    4404: "Kein offenes Terminal für diesen Lauf und Schritt.",
    4409: "Terminal ist schon verbunden (nur eine Verbindung).",
    4429: f"Schon {MAX_TERMINALS} Terminals offen. Eines schließen.",
}

EXIT_UNAVAILABLE = 126
EXIT_TIMEOUT = 124
EXIT_HANGUP = 129
EXIT_ABORT = 130

Publish = Callable[[dict[str, Any]], None]


class _Size(StrictModel):
    cols: int = Field(ge=1, le=500)
    rows: int = Field(ge=1, le=500)


class WsOpen(_Size):
    """First client message: window size; the process starts after it."""

    type: Literal["open"]


class WsResize(_Size):
    """Client text message: new window size."""

    type: Literal["resize"]


_OPEN: TypeAdapter[WsOpen] = TypeAdapter(WsOpen)
_RESIZE: TypeAdapter[WsResize] = TypeAdapter(WsResize)


def transcript_dir() -> Path:
    """Folder of the output transcripts (not created)."""
    return paths.cache_dir() / "terminal"


class _Transcript:
    """Program output only, masked line by line before writing.

    Chunk boundaries are bridged: the unfinished line is held back, and a line over 64 KiB
    keeps its last ``len(longest secret) - 1`` characters for the next chunk. Best effort:
    a secret split by the program itself (cursor movement, redraw) can still slip through.
    """

    def __init__(self, run_id: str, step_id: str, secrets: Sequence[str]) -> None:
        folder = transcript_dir()
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        folder.chmod(0o700)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        for n in range(1, 1000):  # retries and foreach run the same step again
            self.name = f"{run_id}-{step_id}{'' if n == 1 else f'-{n}'}.txt"
            try:
                fd = os.open(folder / self.name, flags, 0o600)
                break
            except FileExistsError:
                continue
        else:
            raise FileExistsError(f"Kein freier Transkriptname für {run_id}-{step_id}.")
        self._file: IO[str] = os.fdopen(fd, "w", encoding="utf-8")
        self._secrets = secrets
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._rest = ""
        self._keep = max(map(len, secrets), default=1) - 1

    def feed(self, data: bytes) -> None:
        text = self._rest + self._decoder.decode(data)
        head, newline, rest = text.rpartition("\n")
        done = head + newline
        if len(rest) > _LINE_CAP:
            cut = len(rest) - self._keep
            done, rest = done + rest[:cut], rest[cut:]
        self._rest = rest
        if done:
            self._file.write(mask_text(done, self._secrets))

    def close(self) -> None:
        rest = self._rest + self._decoder.decode(b"", final=True)
        self._file.write(mask_text(rest, self._secrets))
        self._file.close()


@dataclass
class _Slot:
    run_id: str
    request: TerminalRequest
    publish: Publish
    transcript: bool
    bwrap_path: str | None = None
    done: threading.Event = field(default_factory=threading.Event)
    connected: bool = False
    exit_code: int = EXIT_HANGUP
    transcript_name: str | None = None
    stopping: bool = False  # server shutdown: end the session with close code 1001


class TerminalHub:
    """Open terminal requests of all runs of one app; at most `MAX_TERMINALS` connected."""

    def __init__(self) -> None:
        self._slots: dict[tuple[str, str], _Slot] = {}
        self._lock = threading.Lock()

    def serve(
        self,
        run_id: str,
        request: TerminalRequest,
        publish: Publish,
        *,
        transcript: bool,
        connect_timeout: float,
    ) -> int:
        """Runner-thread provider: announce the terminal, block until it ends, return its code."""
        step_id = request.step_id
        status = self_test()
        if not status.available:
            text = f"Terminal nicht verfügbar: {status.reason} {status.install_hint}".strip()
            publish({"type": "message", "step_id": step_id, "text": text})
            return EXIT_UNAVAILABLE
        if request.abort.is_set():
            return EXIT_ABORT
        slot = _Slot(run_id, request, publish, transcript, status.bwrap_path)
        with self._lock:
            self._slots[(run_id, step_id)] = slot
        publish(
            {
                "type": "terminal_request",
                "step_id": step_id,
                "command": request.command,  # masked by the runner
                "transcript": transcript,
            }
        )
        deadline = time.monotonic() + connect_timeout
        while not slot.done.wait(_TICK):
            with self._lock:
                if slot.connected or slot.done.is_set():
                    continue  # the socket side ends the process (also on abort) and sets done
                if request.abort.is_set():
                    slot.exit_code = EXIT_ABORT
                elif time.monotonic() > deadline:
                    slot.exit_code = EXIT_TIMEOUT
                else:
                    continue
                slot.done.set()  # under the lock: no late `claim` can start a process now
        if slot.exit_code == EXIT_TIMEOUT and not slot.connected:
            text = "Kein Terminal verbunden. Schritt im Browser öffnen und erneut starten."
            publish({"type": "message", "step_id": step_id, "text": text})
        with self._lock:
            self._slots.pop((run_id, step_id), None)
        publish(
            {
                "type": "terminal_closed",
                "step_id": step_id,
                "exit_code": slot.exit_code,
                "transcript": slot.transcript_name,
            }
        )
        return slot.exit_code

    def claim(self, run_id: str, step_id: str) -> _Slot | int:
        """Take the terminal for one connection, or return the WebSocket close code."""
        with self._lock:
            slot = self._slots.get((run_id, step_id))
            if slot is None or slot.done.is_set():
                return 4404
            if slot.connected:
                return 4409
            if sum(s.connected for s in self._slots.values()) >= MAX_TERMINALS:
                return 4429
            slot.connected = True
            return slot

    def release(self, slot: _Slot) -> None:
        """Give an unused claim back (bad `open`); the provider keeps waiting."""
        with self._lock:
            slot.connected = False

    def finish(self, slot: _Slot, exit_code: int, transcript: str | None) -> None:
        """Hand the result to the waiting provider."""
        with self._lock:
            slot.exit_code, slot.transcript_name = exit_code, transcript
            slot.done.set()

    def shutdown(self, timeout: float = 5.0) -> None:
        """End every open terminal (process terminated, socket closed with 1001); idempotent."""
        with self._lock:
            slots = list(self._slots.values())
            for slot in slots:
                slot.stopping = True
                slot.request.abort.set()  # also ends slots nobody has connected yet
        deadline = time.monotonic() + timeout
        for slot in slots:
            if not slot.done.wait(max(0.0, deadline - time.monotonic())):
                logger.warning("Terminal %s beendet sich nicht rechtzeitig", slot.request.step_id)


def terminal_hub(app: FastAPI) -> TerminalHub:
    """The app's hub, created on first use."""
    hub: TerminalHub | None = getattr(app.state, "terminals", None)
    if hub is None:
        hub = app.state.terminals = TerminalHub()
    return hub


router = APIRouter()


async def _first_open(websocket: WebSocket, request: TerminalRequest) -> WsOpen | None:
    """Wait for the `open` message; None on a bad message, disconnect, abort or idle."""
    deadline = time.monotonic() + IDLE_TIMEOUT
    receive = asyncio.ensure_future(websocket.receive())
    try:
        while not receive.done():
            if request.abort.is_set() or time.monotonic() > deadline:
                return None
            await asyncio.wait({receive}, timeout=_TICK)
    finally:
        receive.cancel()
    try:
        message = receive.result()
    except (WebSocketDisconnect, RuntimeError):
        return None
    if message["type"] != "websocket.receive" or message.get("text") is None:
        return None
    try:
        return _OPEN.validate_json(message["text"])
    except ValidationError:
        return None


def _write_some(fd: int, data: bytes) -> int:
    """One non-blocking write; raises BlockingIOError when the PTY is full."""
    return os.write(fd, data)


class _Session:
    """One connected PTY: output pump, input, watchdog. Runs on the event loop only."""

    def __init__(
        self,
        websocket: WebSocket,
        slot: _Slot,
        process: PtyProcess,
        transcript: _Transcript | None,
    ) -> None:
        self.websocket = websocket
        self.slot = slot
        self.process = process
        self.transcript = transcript
        self.loop = asyncio.get_running_loop()
        self.out: asyncio.Queue[bytes] = asyncio.Queue()
        self.backlog = 0  # bytes read but not yet sent
        self.paused = False  # reader removed because the client is slow
        self.pending = bytearray()  # keystrokes the program has not taken yet
        self.eof = False
        self.end: tuple[int, int, str] | None = None  # set by callbacks, reported by `watch`
        self.last = time.monotonic()

    def on_readable(self) -> None:
        try:
            data = self.process.read(MAX_CHUNK)
        except BlockingIOError:
            return
        if not data:
            self.loop.remove_reader(self.process.fd)
            self.eof = True
            return
        self.last = time.monotonic()
        if self.transcript is not None:
            try:
                self.transcript.feed(data)
            except OSError as err:
                self.loop.remove_reader(self.process.fd)
                logger.warning("Terminal-Transkript nicht schreibbar: %s", err)
                text = (
                    f"Transkript nicht schreibbar: {err}. "
                    f"Platz und Rechte von {transcript_dir()} prüfen."
                )
                self.slot.publish(
                    {"type": "message", "step_id": self.slot.request.step_id, "text": text}
                )
                self.end = (EXIT_HANGUP, 1011, "Transkript nicht schreibbar")
                return
        self.backlog += len(data)
        self.out.put_nowait(data)
        if self.backlog > MAX_BACKLOG:  # brake, do not drop: resume at half (in `send`)
            self.loop.remove_reader(self.process.fd)
            self.paused = True

    async def send(self) -> None:
        while True:
            data = await self.out.get()
            await self.websocket.send_bytes(data)
            self.backlog -= len(data)
            if self.paused and self.backlog <= MAX_BACKLOG // 2 and self.end is None:
                self.paused = False
                self.loop.add_reader(self.process.fd, self.on_readable)

    def write(self, data: bytes) -> None:
        """Queue keystrokes; never blocks the loop. Over 1 MiB pending ends the session."""
        if not self.pending:
            with contextlib.suppress(BlockingIOError):
                data = data[_write_some(self.process.fd, data) :]
            if data:
                self.loop.add_writer(self.process.fd, self.on_writable)
        self.pending += data
        if len(self.pending) > MAX_BACKLOG:
            self.loop.remove_writer(self.process.fd)
            self.pending.clear()
            self.end = (EXIT_HANGUP, 4413, "Eingabe-Rückstau über 1 MiB")

    def on_writable(self) -> None:
        try:
            del self.pending[: _write_some(self.process.fd, bytes(self.pending))]
        except BlockingIOError:
            return
        except OSError:  # program side closed: input is moot
            self.pending.clear()
        if not self.pending:
            self.loop.remove_writer(self.process.fd)

    async def receive(self) -> None:
        while True:
            message = await self.websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            data = message.get("bytes")
            if data is not None:
                self.last = time.monotonic()
                try:
                    self.write(data)
                except OSError:
                    await self._error("Terminal nimmt keine Eingaben an.")
                continue
            try:
                size = _RESIZE.validate_json(message.get("text") or "")
            except ValidationError:
                await self._error("Erwartet Binärdaten oder {type: resize, cols, rows}.")
                continue
            with contextlib.suppress(OSError):
                self.process.resize(size.cols, size.rows)

    async def _error(self, text: str) -> None:
        await self.websocket.send_json({"type": "error", "message": text})

    async def watch(self, hard_deadline: float) -> tuple[int, int, str]:
        """Return (exit code for the runner, close code, close reason) once the session ends."""
        abort = self.slot.request.abort
        while True:
            await asyncio.sleep(_TICK)
            now = time.monotonic()
            if self.end is not None:
                return self.end
            if self.eof and self.backlog == 0 and self.process.poll() is not None:
                code = self.process.poll() or 0
                code = 128 - code if code < 0 else code
                return code, 1000, f"exit:{code}"
            if self.slot.stopping:
                return EXIT_ABORT, 1001, "Server wird beendet"
            if abort.is_set():
                return EXIT_ABORT, 1000, "aborted"
            if now - self.last > IDLE_TIMEOUT:
                return EXIT_TIMEOUT, 4408, "15 Minuten ohne Ein- oder Ausgabe"
            if now > hard_deadline:
                return EXIT_TIMEOUT, 4408, "Zeitlimit des Schritts erreicht"


async def _run_session(
    websocket: WebSocket, slot: _Slot, process: PtyProcess, transcript: _Transcript | None
) -> int:
    """Pump until exit, abort, timeout or disconnect; always terminates the process."""
    session = _Session(websocket, slot, process, transcript)
    loop = asyncio.get_running_loop()
    timeout = slot.request.timeout
    hard = time.monotonic() + (min(timeout, _MAX_TIMEOUT) if timeout > 0 else _MAX_TIMEOUT)
    close: tuple[int, str] | None = None
    exit_code = EXIT_HANGUP  # disconnect
    try:
        loop.add_reader(process.fd, session.on_readable)
        sender = asyncio.create_task(session.send())
        receiver = asyncio.create_task(session.receive())
        watcher = asyncio.create_task(session.watch(hard))
        tasks = {sender, receiver, watcher}
        try:  # the sender never ends by itself; the watcher waits until it has sent everything
            await asyncio.wait({receiver, watcher}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            # wait, not gather: gather can re-raise a child's CancelledError, which an
            # outer (anyio) cancel scope does not recognise as its own and lets escape
            await asyncio.wait(tasks)
        for task in tasks:
            error = None if task.cancelled() else task.exception()
            if isinstance(error, Exception) and not isinstance(error, WebSocketDisconnect):
                # type and cause only; exceptions here never carry keystrokes
                logger.warning("Terminal-Sitzung: %s: %s", type(error).__name__, error)
        if watcher.done() and not watcher.cancelled() and watcher.exception() is None:
            exit_code, code, reason = watcher.result()
            close = (code, reason)
    finally:
        if process.fd >= 0:
            loop.remove_reader(process.fd)
            loop.remove_writer(process.fd)
        if transcript is not None:
            transcript.close()
        # A plain thread, started synchronously: the kill must happen even when this task
        # is being cancelled (server shutdown), where an executor job may never start.
        killer = threading.Thread(target=process.terminate, daemon=True, name="wts-pty-kill")
        killer.start()
        while killer.is_alive():
            await asyncio.sleep(_TICK)
    if close is not None:
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):  # client already gone
            await websocket.close(code=close[0], reason=close[1])
    return exit_code


@router.websocket("/ws/runs/{run_id}/terminal/{step_id}")
async def terminal_socket(websocket: WebSocket, run_id: str, step_id: str) -> None:
    """PTY of one terminal step: binary frames both ways, text only for resize."""
    hub = terminal_hub(websocket.app)
    slot = hub.claim(run_id, step_id)
    if isinstance(slot, int):
        await websocket.accept()  # close codes before accept reach the browser only as 1006
        await websocket.close(code=slot, reason=_REFUSED[slot])
        return
    try:
        await websocket.accept()
        opened = await _first_open(websocket, slot.request)
        if opened is None:
            with contextlib.suppress(WebSocketDisconnect, RuntimeError):
                reason = "Erste Nachricht: {type: open, cols, rows}"
                await websocket.close(code=1008, reason=reason)
            return
        await _start(websocket, hub, slot, opened)
    finally:
        if not slot.done.is_set():
            hub.release(slot)  # no process ran; the provider keeps waiting (or times out)


async def _start(websocket: WebSocket, hub: TerminalHub, slot: _Slot, opened: WsOpen) -> None:
    request = slot.request
    transcript = None
    try:
        if slot.transcript:
            transcript = _Transcript(slot.run_id, request.step_id, request.secrets)
            slot.transcript_name = transcript.name
        # ponytail: a cancel during spawn (server shutdown) leaves the process to
        # bwrap --die-with-parent; a cancel-aware spawn thread if shutdown must not wait for that
        process = await asyncio.to_thread(
            spawn,
            request.argv,
            workdir=request.cwd,
            env=request.env,
            cols=opened.cols,
            rows=opened.rows,
            network=request.network,
            bwrap_path=slot.bwrap_path,
        )
    except (TerminalUnavailable, ValueError, OSError) as err:
        if transcript is not None:
            transcript.close()
        text = f"Terminal startet nicht: {err}"  # TerminalUnavailable includes install_hint
        slot.publish({"type": "message", "step_id": request.step_id, "text": text})
        hub.finish(slot, EXIT_UNAVAILABLE, slot.transcript_name)
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await websocket.close(code=1011, reason="Terminal startet nicht")
        return
    exit_code = EXIT_HANGUP
    try:
        exit_code = await _run_session(websocket, slot, process, transcript)
    finally:
        hub.finish(slot, exit_code, slot.transcript_name)


@router.get("/api/terminal/transcripts")
def list_transcripts() -> list[dict[str, Any]]:
    """Saved output transcripts, newest first."""
    folder = transcript_dir()
    if not folder.is_dir():
        return []
    files = [(p, p.stat()) for p in folder.iterdir() if p.is_file() and p.suffix == ".txt"]
    files.sort(key=lambda item: item[1].st_mtime, reverse=True)
    return [{"name": p.name, "size": st.st_size, "mtime": st.st_mtime} for p, st in files]


def delete_transcript(name: str) -> None:
    """Delete one transcript by name (no path part).

    Raises:
        ValueError: The name is not a transcript name.
        FileNotFoundError: No such transcript.
    """
    folder = transcript_dir()
    path = folder / name
    if not _TRANSCRIPT_NAME.match(name) or name.startswith(".") or not paths.inside(path, folder):
        raise ValueError(f"Ungültiger Transkriptname '{name}'. Erlaubt: Name aus der Liste.")
    try:
        path.unlink()
    except FileNotFoundError:
        raise FileNotFoundError(f"Transkript '{name}' nicht gefunden.") from None


@router.delete("/api/terminal/transcripts/{name}", status_code=204)
def delete_transcript_route(name: str) -> Response:
    """Delete one transcript (name only, no path)."""
    try:
        delete_transcript(name)
    except ValueError as err:
        return error_response(422, "name", str(err))
    except FileNotFoundError as err:
        return error_response(404, "not_found", str(err))
    return Response(status_code=204)
