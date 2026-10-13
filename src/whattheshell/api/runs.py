# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run endpoints: create/plan, start, control, confirm and the live WebSocket (see docs/API.md)."""

import asyncio
import contextlib
import dataclasses
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from pydantic import TypeAdapter, ValidationError

from whattheshell import paths
from whattheshell.api.errors import error_response, validation_errors
from whattheshell.api.terminal import MAX_TERMINALS as MAX_TERMINALS  # defined there: no cycle
from whattheshell.api.terminal import TerminalHub, terminal_hub
from whattheshell.catalog import Catalog
from whattheshell.engine import (
    ConfirmRequest,
    Controller,
    Event,
    Prepared,
    RunError,
    Runner,
    TerminalRequest,
    WorkflowFinished,
    plan,
    plan_text,
)
from whattheshell.models.common import StrictModel
from whattheshell.models.workflow import Workflow
from whattheshell.safety import needs_confirmation, summarize

logger = logging.getLogger(__name__)

MAX_EVENTS = 10_000
MAX_FINISHED_RUNS = 50
MAX_CREATED_RUNS = 20
MAX_RUNNING_RUNS = 4
CONFIRM_TIMEOUT = 600.0

_EVENT_TYPES = {
    "StepStarted": "step_started",
    "OutputChunk": "output",
    "StepFinished": "step_finished",
    "StepSkipped": "step_skipped",
    "Message": "message",
}


class RunBody(StrictModel):
    """Request body of `POST /api/runs`."""

    document: dict[str, Any]
    variables: dict[str, str] = {}
    cwd: str | None = None
    dry_run: bool = False
    transcript: bool = False  # save terminal output (SECURITY.md 7.4), off by default


class ControlBody(StrictModel):
    """Request body of `POST /api/runs/{id}/control`."""

    action: Literal["abort", "pause", "resume", "step"]


class ConfirmBody(StrictModel):
    """Request body of `POST /api/runs/{id}/confirm`."""

    step_id: str
    ok: bool


class WsConfirm(StrictModel):
    """WebSocket message: answer to a `confirm_request`."""

    type: Literal["confirm"]
    step_id: str
    ok: bool


class WsControl(StrictModel):
    """WebSocket message: run control."""

    type: Literal["control"]
    action: Literal["abort", "pause", "resume", "step"]


_WS_MESSAGE: TypeAdapter[WsConfirm | WsControl] = TypeAdapter(WsConfirm | WsControl)


class _Pending:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.answer = False


@dataclass
class RunInfo:
    """One run: its runner, history, live subscribers and open confirmations."""

    run_id: str
    runner: Runner
    prepared: Prepared
    controller: Controller
    cwd: Path
    make_cwd: bool
    workflow_name: str = ""
    started: datetime | None = None
    finished: datetime | None = None
    exit_code: int | None = None
    status: Literal["created", "running", "success", "failed", "aborted"] = "created"
    events: list[dict[str, Any]] = field(default_factory=list)
    pending: dict[str, _Pending] = field(default_factory=dict)
    subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]] = field(
        default_factory=list
    )
    lock: threading.Lock = field(default_factory=threading.Lock)
    thread: threading.Thread | None = None

    def publish(self, event: dict[str, Any]) -> None:
        """Append to the history (bounded) and hand over to every subscriber; thread-safe."""
        with self.lock:
            self.events.append(event)
            if len(self.events) > MAX_EVENTS:
                # ponytail: linear scan per overflow, ring buffer if runs get very chatty
                for index, old in enumerate(self.events):
                    if old["type"] == "output":
                        del self.events[index]
                        break
            for loop, queue in list(self.subscribers):
                try:
                    loop.call_soon_threadsafe(queue.put_nowait, event)
                except RuntimeError:  # client's loop is gone
                    self.subscribers.remove((loop, queue))

    def subscribe(self) -> tuple[asyncio.Queue[dict[str, Any]], list[dict[str, Any]]]:
        """Register the running loop; returns the queue and the history up to now (no gap)."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self.lock:
            self.subscribers.append((asyncio.get_running_loop(), queue))
            return queue, list(self.events)

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove a subscriber."""
        with self.lock:
            self.subscribers = [s for s in self.subscribers if s[1] is not queue]

    def ask(self, request: ConfirmRequest) -> bool:
        """Runner-thread confirmer: publish the question and wait for the answer."""
        if self.controller.abort.is_set():
            return False
        pending = _Pending()
        self.pending[request.step_id] = pending
        self.publish(
            {
                "type": "confirm_request",
                "step_id": request.step_id,
                "command": request.command,
                "safety": request.safety.value,
                "reasons": list(request.reasons),
            }
        )
        if self.controller.abort.is_set():  # abort raced with registration
            pending.event.set()
        answered = pending.event.wait(CONFIRM_TIMEOUT)
        self.pending.pop(request.step_id, None)
        return answered and pending.answer

    def answer(self, step_id: str, ok: bool) -> bool:
        """Resolve an open confirmation; False if none is waiting for `step_id`."""
        pending = self.pending.get(step_id)
        if pending is None:
            return False
        pending.answer = ok
        pending.event.set()
        return True

    def control(self, action: str) -> None:
        """Apply abort/pause/resume/step; abort also declines open confirmations."""
        ctl = self.controller
        match action:
            case "abort":
                ctl.abort.set()
                for pending in list(self.pending.values()):
                    pending.answer = False
                    pending.event.set()
            case "pause":
                ctl.pause.set()
            case "resume":
                ctl.pause.clear()
            case "step":
                ctl.step_mode = True
                ctl.step_release.set()

    def _on_event(self, event: Event) -> None:
        if isinstance(event, WorkflowFinished):
            return  # published by `_run` together with the exit code
        data = dataclasses.asdict(event)
        for key, value in data.items():
            data[key] = getattr(value, "value", value)
        self.publish({"type": _EVENT_TYPES[type(event).__name__], **data})

    def _run(self) -> None:
        try:
            result = self.runner.run(self.prepared)
            status, message, exit_code = result.status, result.message, result.exit_code
        except Exception as err:  # noqa: BLE001 - reported to the client, never swallowed
            logger.exception("Lauf %s abgestürzt", self.run_id)
            status, message, exit_code = "failed", f"Interner Fehler: {err}", 1
        self.status = status
        self.finished = datetime.now().astimezone()
        self.exit_code = exit_code
        self.publish(
            {"type": "finished", "status": status, "message": message, "exit_code": exit_code}
        )

    def start(self) -> bool:
        """Create the run folder if it is ours, then start the daemon thread.

        Returns False if the run was already started; raises OSError if the folder fails.
        """
        with self.lock:
            if self.status != "created":
                return False
            if self.make_cwd:
                self.cwd.mkdir(parents=True, exist_ok=True)
            self.status = "running"
            self.started = datetime.now().astimezone()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True


class RunManager:
    """All runs of the app, newest last."""

    def __init__(self, terminals: TerminalHub) -> None:
        self._runs: dict[str, RunInfo] = {}
        self._lock = threading.Lock()
        self.terminals = terminals

    def get(self, run_id: str) -> RunInfo | None:
        """Look up a run."""
        return self._runs.get(run_id)

    def create(
        self,
        document: dict[str, Any],
        variables: dict[str, str],
        cwd: Path | None,
        catalog: Catalog,
        transcript: bool = False,
    ) -> tuple[RunInfo, dict[str, Any]]:
        """Validate and prepare a run; returns it with the response body (nothing executed).

        Raises:
            ValidationError: The document is not a valid workflow.
            RunError: Variables or tools are not usable.
        """
        workflow = Workflow.model_validate(document)
        run_id = secrets.token_hex(8)
        make_cwd = cwd is None
        if cwd is None:
            cwd = paths.config_dir() / "runs" / run_id  # created by `RunInfo.start`
        controller = Controller()
        holder: list[RunInfo] = []

        def terminal(request: TerminalRequest) -> int:
            return self.terminals.serve(
                run_id,
                request,
                holder[0].publish,
                transcript=transcript,
                connect_timeout=CONFIRM_TIMEOUT,
            )

        runner = Runner(
            catalog,
            confirm=lambda request: holder[0].ask(request),
            on_event=lambda event: holder[0]._on_event(event),  # noqa: SLF001
            controller=controller,
            cwd=cwd,
            terminal=terminal,
        )
        prepared = runner.prepare(workflow, variables)
        info = RunInfo(
            run_id, runner, prepared, controller, cwd, make_cwd, workflow_name=workflow.name
        )
        holder.append(info)
        max_safety = summarize(list(prepared.verdicts.items()))
        body = {
            "run_id": run_id,
            "cwd": str(cwd),
            "plan": plan_text(plan(prepared)),
            "needs_confirmation": needs_confirmation(max_safety),
            "max_safety": max_safety.value,
        }
        return info, body

    def add(self, info: RunInfo) -> None:
        """Keep the run; drop the oldest finished ones beyond the limit."""
        with self._lock:
            self._runs[info.run_id] = info
            finished = [
                r for r in self._runs.values() if r.status in ("success", "failed", "aborted")
            ]
            created = [r for r in self._runs.values() if r.status == "created"]
            doomed = finished[: max(0, len(finished) - MAX_FINISHED_RUNS)]
            doomed += created[: max(0, len(created) - MAX_CREATED_RUNS)]
            for old in doomed:
                del self._runs[old.run_id]

    def recent(self) -> list[RunInfo]:
        """Started runs, newest first."""
        with self._lock:
            runs = [r for r in self._runs.values() if r.started is not None]
        return sorted(runs, key=lambda r: r.started or datetime.min, reverse=True)

    def start(self, info: RunInfo) -> Literal["started", "already", "busy"]:
        """Start `info` unless it ran before or too many runs are active."""
        with self._lock:
            if sum(r.status == "running" for r in self._runs.values()) >= MAX_RUNNING_RUNS:
                return "busy"
            return "started" if info.start() else "already"

    def shutdown(self, timeout: float = 5.0) -> None:
        """Abort every running run and join the runner threads for up to `timeout` seconds."""
        with self._lock:
            running = [r for r in self._runs.values() if r.status == "running"]
        for info in running:
            info.control("abort")
        deadline = time.monotonic() + timeout
        for info in running:
            if info.thread is not None:
                info.thread.join(max(0.0, deadline - time.monotonic()))
            if info.thread is not None and info.thread.is_alive():
                logger.warning("Lauf %s beendet sich nicht rechtzeitig", info.run_id)


router = APIRouter()


def run_manager(app: FastAPI) -> RunManager:
    """The app's run manager, created on first use."""
    manager: RunManager | None = getattr(app.state, "runs", None)
    if manager is None:
        manager = app.state.runs = RunManager(terminal_hub(app))
    return manager


def _unknown(run_id: str) -> Response:
    return error_response(404, "not_found", f"Lauf '{run_id}' unbekannt")


def create_run_response(
    app: FastAPI,
    document: dict[str, Any],
    variables: dict[str, str],
    cwd_text: str | None,
    dry_run: bool,
    transcript: bool = False,
) -> Response:
    """Validate, prepare and plan a run; with `dry_run` nothing is kept or created."""
    cwd = Path(cwd_text) if cwd_text else None
    if cwd is not None:
        if not cwd.is_absolute() or not cwd.is_dir():
            message = f"cwd '{cwd_text}' muss ein existierender absoluter Ordner sein"
            return error_response(
                422, "invalid_cwd", message, [{"path": "cwd", "message": message}]
            )
        cwd = cwd.resolve()
    try:
        info, answer = run_manager(app).create(
            document, variables, cwd, app.state.catalog, transcript
        )
    except ValidationError as err:
        return error_response(422, "validation", "Workflow ungültig", validation_errors(err))
    except RunError as err:
        return error_response(422, "run", str(err), [{"path": "", "message": str(err)}])
    if not dry_run:
        run_manager(app).add(info)
    return JSONResponse(answer)


@router.post("/api/runs")
def create_run(body: RunBody, request: Request) -> Response:
    """Validate, prepare and plan a run; with `dry_run` nothing is kept or created."""
    return create_run_response(
        request.app, body.document, body.variables, body.cwd, body.dry_run, body.transcript
    )


@router.get("/api/runs")
def list_runs(request: Request) -> list[dict[str, Any]]:
    """The last started runs (at most 50), newest first."""
    return [
        {
            "run_id": r.run_id,
            "status": r.status,
            "workflow_name": r.workflow_name,
            "started": r.started.isoformat() if r.started else None,
            "finished": r.finished.isoformat() if r.finished else None,
            "exit_code": r.exit_code,
        }
        for r in run_manager(request.app).recent()[:MAX_FINISHED_RUNS]
    ]


@router.post("/api/runs/{run_id}/start", status_code=202)
def start_run(run_id: str, request: Request) -> Response:
    """Start the run in the background; a second start is a conflict."""
    manager = run_manager(request.app)
    info = manager.get(run_id)
    if info is None:
        return _unknown(run_id)
    try:
        outcome = manager.start(info)
    except OSError as err:
        return error_response(500, "cwd", f"Laufordner nicht anlegbar: {err}")
    if outcome == "busy":
        return error_response(
            429,
            "too_many_runs",
            f"Es laufen bereits {MAX_RUNNING_RUNS} Läufe. "
            "Einen abbrechen oder abwarten, dann erneut starten.",
        )
    if outcome == "already":
        return error_response(409, "already_started", f"Lauf '{run_id}' wurde bereits gestartet")
    return Response(status_code=202)


@router.get("/api/runs/{run_id}")
def get_run(run_id: str, request: Request) -> Response:
    """Status and event history."""
    info = run_manager(request.app).get(run_id)
    if info is None:
        return _unknown(run_id)
    with info.lock:
        return JSONResponse({"status": info.status, "events": list(info.events)})


@router.post("/api/runs/{run_id}/control", status_code=204)
def control_run(run_id: str, body: ControlBody, request: Request) -> Response:
    """Abort, pause, resume or single-step the run."""
    info = run_manager(request.app).get(run_id)
    if info is None:
        return _unknown(run_id)
    info.control(body.action)
    return Response(status_code=204)


@router.post("/api/runs/{run_id}/confirm", status_code=204)
def confirm_run(run_id: str, body: ConfirmBody, request: Request) -> Response:
    """Answer a `confirm_request`."""
    info = run_manager(request.app).get(run_id)
    if info is None:
        return _unknown(run_id)
    if not info.answer(body.step_id, body.ok):
        return error_response(
            404, "no_confirmation", f"Keine offene Bestätigung für Schritt '{body.step_id}'"
        )
    return Response(status_code=204)


async def _send(
    websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]], history: list[dict[str, Any]]
) -> None:
    """History first, then live events; ends after `finished`."""
    for event in history:
        await websocket.send_json(event)
        if event["type"] == "finished":
            return
    while True:
        event = await queue.get()
        await websocket.send_json(event)
        if event["type"] == "finished":
            return


async def _receive(websocket: WebSocket, info: RunInfo) -> None:
    """Client messages `confirm` and `control`; bad ones get an error reply."""
    while True:
        text = await websocket.receive_text()
        try:
            message = _WS_MESSAGE.validate_json(text)  # bad JSON is a ValidationError, too
        except ValidationError as err:
            logger.warning("WS: ungültige Nachricht %.200r", text)
            reason = err.errors()[0]["msg"]
            await websocket.send_json(
                {"type": "error", "message": f"Ungültige Nachricht: {reason}"}
            )
            continue
        if isinstance(message, WsControl):
            info.control(message.action)
        elif not info.answer(message.step_id, message.ok):
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Keine offene Bestätigung für Schritt '{message.step_id}'",
                }
            )


@router.websocket("/ws/runs/{run_id}")
async def run_socket(websocket: WebSocket, run_id: str) -> None:
    """Stream events of a run (history first) and accept confirm/control messages."""
    info = run_manager(websocket.app).get(run_id)
    if info is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    queue, history = info.subscribe()
    sender = asyncio.create_task(_send(websocket, queue, history))
    receiver = asyncio.create_task(_receive(websocket, info))
    try:
        await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        info.unsubscribe(queue)
        for task in (sender, receiver):
            task.cancel()
        # wait, not gather: gather can re-raise a child's CancelledError, which the
        # server's (anyio) cancel scope does not recognise as its own and lets escape
        await asyncio.wait({sender, receiver})
        for task in (sender, receiver):  # retrieve, so asyncio does not warn
            if not task.cancelled():
                task.exception()
    with contextlib.suppress(WebSocketDisconnect, RuntimeError):  # client already gone
        await websocket.close()
