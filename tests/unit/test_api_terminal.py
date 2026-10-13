# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
import json
import os
import shutil
import stat
import time
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from whattheshell import cli, sandbox, terminal
from whattheshell.api import runs as runs_api
from whattheshell.api import terminal as terminal_api
from whattheshell.api.app import create_app
from whattheshell.api.security import Session
from whattheshell.catalog import Catalog
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.sandbox import SandboxStatus

PORT = 48124
TOKEN = "secret-token"
HEADERS = {"X-WTS-Token": TOKEN}
SECRET = "s3cr3t-value"

needs_bwrap = pytest.mark.skipif(
    shutil.which("bwrap") is None, reason="bwrap not installed: terminal needs the sandbox"
)


class FakePty:
    """PtyProcess stand-in on a real PTY pair: the test writes program output to `slave`."""

    def __init__(self) -> None:
        self.fd, self.slave = os.openpty()
        os.set_blocking(self.fd, False)
        self.pid = os.getpid()
        self.code: int | None = None
        self.written: list[bytes] = []  # filled by the patched `_write_some`
        self.blocked = False  # True: the program never reads its input

    def read(self, max_bytes: int = 65536) -> bytes:
        try:
            return os.read(self.fd, max_bytes)
        except BlockingIOError:
            raise
        except OSError:
            return b""

    def resize(self, cols: int, rows: int) -> None:
        pass

    def poll(self) -> int | None:
        return self.code

    def terminate(self) -> None:
        if self.code is None:
            self.code = -1
        for fd in (self.fd, self.slave):
            if fd >= 0:
                os.close(fd)
        self.fd = self.slave = -1

    def exit(self, code: int) -> None:
        """Program ends: last slave fd closes (EOF on the master)."""
        self.code = code
        os.close(self.slave)
        self.slave = -1


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdgcache"))
    registry = ModuleRegistry([])
    app = create_app(
        Session(port=PORT, token=TOKEN),
        catalog=Catalog(tmp_path / "cache", registry),
        registry=registry,
        static_dir=tmp_path,
    )
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}", headers=HEADERS)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> list[FakePty]:
    """Sandbox reported available, `spawn` returns FakePty objects (collected here)."""
    spawned: list[FakePty] = []

    def fake_spawn(*_a: Any, **_k: Any) -> FakePty:
        spawned.append(FakePty())
        return spawned[-1]

    def write_some(fd: int, data: bytes) -> int:
        (fake,) = [f for f in spawned if f.fd == fd]
        if fake.blocked:
            raise BlockingIOError
        fake.written.append(bytes(data))
        return len(data)

    ok = SandboxStatus(True, "", "", "/usr/bin/bwrap")
    monkeypatch.setattr(terminal_api, "self_test", lambda: ok)
    monkeypatch.setattr(terminal_api, "spawn", fake_spawn)
    monkeypatch.setattr(terminal_api, "_write_some", write_some)
    return spawned


def doc(*steps: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "t",
        "variables": {"pw": {"type": "secret", "required": False}},
        "steps": list(steps),
    }


TERM = {"id": "t", "kind": "terminal", "tool": "cat"}
AFTER = {"id": "after", "tool": "echo", "extra_args": ["danach"]}


def ws_url(path: str) -> str:
    return f"{path}?token={TOKEN}"


def start(client: TestClient, document: dict[str, Any], **extra: Any) -> str:
    response = client.post(
        "/api/runs", json={"document": document, "variables": {"pw": SECRET}, **extra}
    )
    assert response.status_code == 200, response.text
    run_id: str = response.json()["run_id"]
    assert client.post(f"/api/runs/{run_id}/start").status_code == 202
    return run_id


def until(ws: WebSocketTestSession, wanted: str) -> list[dict[str, Any]]:
    """Read run events up to `wanted`, accepting every confirmation on the way."""
    events = []
    while True:
        events.append(ws.receive_json())
        if events[-1]["type"] == "confirm_request":
            ws.send_json({"type": "confirm", "step_id": events[-1]["step_id"], "ok": True})
        if events[-1]["type"] in (wanted, "finished"):
            return events


def open_terminal(client: TestClient, run_id: str, step: str = "t") -> Any:
    return connect(client, f"/ws/runs/{run_id}/terminal/{step}")


def connect(client: TestClient, path: str) -> Any:
    return client.websocket_connect(ws_url(path), headers={"Host": f"127.0.0.1:{PORT}"})


def closed_code(ws: WebSocketTestSession) -> tuple[int, str]:
    while True:
        message = ws.receive()
        if message["type"] == "websocket.close":
            return message["code"], message.get("reason") or ""


def wait_for(check: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "timeout"
        time.sleep(0.02)


# ------------------------------------------------------------------ 7.7 Nr. 1


def test_terminal_ws_needs_token_origin_host(client: TestClient, fakes: list[FakePty]) -> None:
    run_id = start(client, doc(TERM))
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        until(run_ws, "terminal_request")
        path = f"/ws/runs/{run_id}/terminal/t"
        host = {"Host": f"127.0.0.1:{PORT}"}
        for url, headers, code in (
            (path, host, 4401),
            (f"{path}?token=wrong", host, 4401),
            (ws_url(path), {**host, "Origin": "http://evil.example"}, 4403),
            (ws_url(path), {"Host": "evil.example"}, 4400),
        ):
            with (
                pytest.raises(WebSocketDisconnect) as err,
                client.websocket_connect(url, headers=headers) as ws,
            ):
                ws.send_text(json.dumps({"type": "open", "cols": 80, "rows": 24}))
            assert err.value.code == code
        assert fakes == []
        client.post(f"/api/runs/{run_id}/control", json={"action": "abort"})
        until(run_ws, "finished")


def test_unknown_terminal_is_4404(client: TestClient, fakes: list[FakePty]) -> None:
    with open_terminal(client, "nope") as ws:  # accepted first, so the browser sees the code
        assert closed_code(ws)[0] == 4404
    assert fakes == []


# ------------------------------------------------------------------ 7.7 Nr. 3


def test_fifth_terminal_and_second_connection_rejected(
    client: TestClient, fakes: list[FakePty], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runs_api, "MAX_RUNNING_RUNS", 10)
    run_ids = [start(client, doc(TERM)) for _ in range(5)]
    for run_id in run_ids:
        with connect(client, f"/ws/runs/{run_id}") as run_ws:
            until(run_ws, "terminal_request")
    open_msg = {"type": "open", "cols": 80, "rows": 24}
    sockets = [open_terminal(client, run_id) for run_id in run_ids[:4]]
    entered = [s.__enter__() for s in sockets]
    try:
        for ws in entered:
            ws.send_json(open_msg)
        wait_for(lambda: len(fakes) == 4)
        with open_terminal(client, run_ids[4]) as ws:
            assert closed_code(ws)[0] == 4429
        with open_terminal(client, run_ids[0]) as ws:
            assert closed_code(ws)[0] == 4409
    finally:
        for run_id in run_ids:
            client.post(f"/api/runs/{run_id}/control", json={"action": "abort"})
        for ws in entered:
            assert closed_code(ws) == (1000, "aborted")
        for s in sockets:
            s.__exit__(None, None, None)
    assert len(fakes) == 4


# ------------------------------------------------------------------ 7.7 Nr. 4


def _session_with_input(client: TestClient, fakes: list[FakePty], **extra: Any) -> list[Any]:
    run_id = start(client, doc(TERM, AFTER), **extra)
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        until(run_ws, "terminal_request")
        with open_terminal(client, run_id) as ws:
            ws.send_json({"type": "open", "cols": 80, "rows": 24})
            wait_for(lambda: len(fakes) == 1)
            ws.send_bytes(b"typed-password\r")
            wait_for(lambda: fakes[0].written == [b"typed-password\r"])
            os.write(fakes[0].slave, f"out {SECRET} line\r\nrest".encode())
            assert b"out" in ws.receive_bytes()
            fakes[0].exit(0)
            assert closed_code(ws) == (1000, "exit:0")
        events = until(run_ws, "finished")
    assert events[-1]["status"] == "success"
    history: list[Any] = client.get(f"/api/runs/{run_id}").json()["events"]
    assert "typed-password" not in json.dumps(history)
    return history


def test_no_transcript_without_opt_in(client: TestClient, fakes: list[FakePty]) -> None:
    history = _session_with_input(client, fakes)
    closed = [e for e in history if e["type"] == "terminal_closed"]
    assert closed == [
        {"type": "terminal_closed", "step_id": "t", "exit_code": 0, "transcript": None}
    ]
    assert not terminal_api.transcript_dir().exists()
    assert client.get("/api/terminal/transcripts").json() == []


def test_transcript_opt_in_masked_0600(client: TestClient, fakes: list[FakePty]) -> None:
    history = _session_with_input(client, fakes, transcript=True)
    (closed,) = [e for e in history if e["type"] == "terminal_closed"]
    name = closed["transcript"]
    path = terminal_api.transcript_dir() / name
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    data = path.read_bytes()  # the PTY turns \n into \r\n (onlcr)
    assert data == b"out *** line\r\r\nrest" and b"typed-password" not in data
    (listed,) = client.get("/api/terminal/transcripts").json()
    assert listed["name"] == name and listed["size"] == len(data)
    assert client.delete("/api/terminal/transcripts/..%2Fx.txt").status_code in (404, 422)
    assert client.delete("/api/terminal/transcripts/.x.txt").status_code == 422
    assert client.delete("/api/terminal/transcripts/none.txt").status_code == 404
    assert client.delete(f"/api/terminal/transcripts/{name}").status_code == 204
    assert not path.exists()


def test_transcript_masks_secret_split_across_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(terminal_api, "transcript_dir", lambda: tmp_path)
    transcript = terminal_api._Transcript("r", "s", ["s3cretvalue"])
    transcript.feed(b"pw=s3cr")
    transcript.feed(b"etvalue\n")
    # over the line cap without newline: the tail that could start a secret is held back
    transcript.feed(b"a" * (terminal_api._LINE_CAP + 1) + b"s3cr")
    transcript.feed(b"etvalue end")
    transcript.close()
    text = (tmp_path / transcript.name).read_text()
    assert "s3cr" not in text and text.startswith("pw=***\n") and text.endswith("***" + " end")


# ------------------------------------------------------------------ 7.7 Nr. 5


def test_without_bwrap_no_process(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fakes: list[FakePty]
) -> None:
    monkeypatch.setattr(terminal_api, "self_test", sandbox.self_test)
    run_id = start(client, doc(TERM))  # prepare resolved `cat` already
    monkeypatch.setattr(shutil, "which", lambda *_a, **_k: None)
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        events = until(run_ws, "terminal_request")
    types = [e["type"] for e in events]
    assert "terminal_request" not in types and events[-1]["status"] == "failed"
    (message,) = [e for e in events if e["type"] == "message"]
    assert "bwrap" in message["text"]
    assert fakes == []


# ------------------------------------------------------------- other paths


def test_bad_open_releases_and_no_connection_times_out(
    client: TestClient, fakes: list[FakePty], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runs_api, "CONFIRM_TIMEOUT", 1.0)
    run_id = start(client, doc(TERM))
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        until(run_ws, "terminal_request")
        with open_terminal(client, run_id) as ws:
            ws.send_json({"type": "open", "cols": 0, "rows": 24})
            assert closed_code(ws)[0] == 1008
        events = until(run_ws, "finished")
    assert fakes == []
    assert any("Kein Terminal verbunden" in e.get("text", "") for e in events)
    closed = [e for e in events if e["type"] == "terminal_closed"]
    assert closed[0]["exit_code"] == 124 and events[-1]["status"] == "failed"


def test_bad_text_frame_gets_error(client: TestClient, fakes: list[FakePty]) -> None:
    run_id = start(client, doc(TERM))
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        until(run_ws, "terminal_request")
        with open_terminal(client, run_id) as ws:
            ws.send_json({"type": "open", "cols": 80, "rows": 24})
            ws.send_text("rm -rf /")
            assert ws.receive_json()["type"] == "error"
            ws.send_json({"type": "resize", "cols": 100, "rows": 30})
            wait_for(lambda: len(fakes) == 1)
            fakes[0].exit(3)
            assert closed_code(ws) == (1000, "exit:3")
        events = until(run_ws, "finished")
    assert events[-1]["status"] == "failed" and fakes[0].written == []


# ------------------------------------------------------- real PTY in bwrap


def _real_spawn(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    spawned: list[Any] = []
    real = terminal.spawn

    def recording(*args: Any, **kwargs: Any) -> Any:
        spawned.append(real(*args, **kwargs))
        return spawned[-1]

    monkeypatch.setattr(terminal_api, "spawn", recording)
    return spawned


@needs_bwrap
def test_cat_happy_path_and_next_step(client: TestClient) -> None:
    run_id = start(client, doc(TERM, AFTER))
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        request = until(run_ws, "terminal_request")[-1]
        assert request["type"] == "terminal_request" and request["command"].endswith("cat")
        with open_terminal(client, run_id) as ws:
            ws.send_json({"type": "open", "cols": 80, "rows": 24})
            ws.send_bytes(b"hi\n")
            out = b""
            while b"hi" not in out:
                out += ws.receive_bytes()
            ws.send_bytes(b"\x04")
            assert closed_code(ws) == (1000, "exit:0")
        events = until(run_ws, "finished")
    assert events[-1]["status"] == "success"
    assert {"type": "output", "step_id": "after", "stream": "stdout", "text": "danach\n"} in events


@needs_bwrap
def test_disconnect_kills_group(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    spawned = _real_spawn(monkeypatch)
    step = {**TERM, "tool": "sh", "extra_args": ["-c", "sleep 4242 & wait"]}
    run_id = start(client, doc(step))
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        until(run_ws, "terminal_request")
        with open_terminal(client, run_id) as ws:
            ws.send_json({"type": "open", "cols": 80, "rows": 24})
            wait_for(lambda: len(spawned) == 1)
            pgid = os.getpgid(spawned[0].pid)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        with pytest.raises(ProcessLookupError):
            os.killpg(pgid, 0)
        events = until(run_ws, "finished")
    closed = [e for e in events if e["type"] == "terminal_closed"]
    assert closed[0]["exit_code"] == 129 and events[-1]["status"] == "failed"


def test_cli_transcripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    folder = terminal_api.transcript_dir()
    folder.mkdir(parents=True)
    (folder / "r-t.txt").write_text("x")
    assert cli.main(["terminal", "transcripts"]) == 0
    assert capsys.readouterr().out == "r-t.txt\t1\n"
    assert cli.main(["terminal", "transcripts", "--delete", "../r-t.txt"]) == 1
    assert cli.main(["terminal", "transcripts", "--delete", "r-t.txt"]) == 0
    assert not (folder / "r-t.txt").exists()


def test_workflow_run_shortcut_passes_transcript(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[bool] = []
    real = runs_api.RunManager.create

    def spy(self: runs_api.RunManager, *args: Any) -> Any:
        seen.append(args[-1])
        return real(self, *args)

    monkeypatch.setattr(runs_api.RunManager, "create", spy)
    body = {"dry_run": True, "transcript": True}
    assert client.post("/api/workflows/log_errors/run", json=body).status_code == 200
    assert seen == [True]


def test_blocked_input_is_buffered_then_4413(client: TestClient, fakes: list[FakePty]) -> None:
    run_id = start(client, doc(TERM))
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        until(run_ws, "terminal_request")
        with open_terminal(client, run_id) as ws:
            ws.send_json({"type": "open", "cols": 80, "rows": 24})
            wait_for(lambda: len(fakes) == 1)
            fakes[0].blocked = True
            ws.send_bytes(b"x" * 600_000)  # buffered, the loop is not blocked
            ws.send_json({"type": "nonsense"})
            assert ws.receive_json()["type"] == "error"
            ws.send_bytes(b"x" * 600_000)
            assert closed_code(ws)[0] == 4413
        events = until(run_ws, "finished")
    closed = [e for e in events if e["type"] == "terminal_closed"]
    assert closed[0]["exit_code"] == 129 and fakes[0].written == []


class SlowSocket:
    def __init__(self) -> None:
        self.go = asyncio.Event()
        self.sent = 0

    async def send_bytes(self, data: bytes) -> None:
        await self.go.wait()
        self.sent += len(data)


class EndlessOutput:
    def __init__(self) -> None:
        self.fd, self.other = os.pipe()

    def read(self, max_bytes: int = 65536) -> bytes:
        return b"y" * max_bytes


def test_slow_client_pauses_reading_instead_of_closing() -> None:
    async def scenario() -> None:
        process = EndlessOutput()
        # slot is only used on session end, which this scenario never reaches
        session = terminal_api._Session(
            cast(Any, SlowSocket()), cast(Any, None), cast(Any, process), None
        )
        socket = cast(SlowSocket, session.websocket)
        loop = asyncio.get_running_loop()
        loop.add_reader(process.fd, session.on_readable)
        sender = asyncio.create_task(session.send())
        while not session.paused:
            session.on_readable()
        assert session.backlog > terminal_api.MAX_BACKLOG and session.end is None
        socket.go.set()
        while session.paused:
            await asyncio.sleep(0)
        assert session.backlog <= terminal_api.MAX_BACKLOG // 2 and socket.sent > 0
        sender.cancel()
        loop.remove_reader(process.fd)
        os.close(process.fd)
        os.close(process.other)

    asyncio.run(scenario())
