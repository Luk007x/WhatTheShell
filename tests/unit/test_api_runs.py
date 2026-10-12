# SPDX-License-Identifier: AGPL-3.0-or-later
import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from whattheshell.api.runs import router
from whattheshell.catalog import Catalog

_PREAMBLE = """#!/bin/sh
case "$1" in
  --help)
    printf 'Usage: %s [OPTION]... [ARG]...\\n\\nTest tool.\\n\\n' "${0##*/}"
    printf 'Options:\\n  -v, --verbose  verbose\\n'
    exit 0;;
  --version) echo "1.0"; exit 0;;
esac
"""


@pytest.fixture
def counter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Test scripts first on PATH; `cp` (caution by name) appends to the returned file."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    counter = tmp_path / "counter"
    bodies = {
        "echo-args": 'for a in "$@"; do printf \'%s\\n\' "$a"; done',
        "napper": "sleep 5",
        "nap": "sleep 0.5",
        "cp": f'echo run >> "{counter}"',
    }
    for name, body in bodies.items():
        path = bin_dir / name
        path.write_text(_PREAMBLE + body + "\n")
        path.chmod(0o755)
    sh = Path(shutil.which("sh") or "/bin/sh").parent
    monkeypatch.setenv("PATH", f"{bin_dir}:{sh}:/usr/bin:/bin")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return counter


@pytest.fixture
def client(counter: Path, tmp_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.catalog = Catalog(cache_dir=tmp_path / "cache")
    app.state.registry = None
    return TestClient(app)


def doc(*steps: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "name": "t", "steps": list(steps)}


ECHO = {"id": "a", "tool": "echo-args", "extra_args": ["hi"]}
COPY = {"id": "c", "tool": "cp"}
NAP = {"id": "n", "tool": "napper"}
SHORT = [{"id": "s1", "tool": "nap"}, {"id": "s2", "tool": "nap"}]


def create(client: TestClient, document: dict[str, Any], **extra: Any) -> dict[str, Any]:
    response = client.post("/api/runs", json={"document": document, **extra})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def read_until_finished(ws: WebSocketTestSession) -> list[dict[str, Any]]:
    events = []
    while True:
        events.append(ws.receive_json())
        if events[-1]["type"] == "finished":
            return events


def test_dry_run_returns_plan_without_run(client: TestClient) -> None:
    body = create(client, doc(ECHO), dry_run=True)
    assert body["needs_confirmation"] is False and body["max_safety"] == "safe"
    assert "echo-args" in body["plan"]
    assert client.get(f"/api/runs/{body['run_id']}").status_code == 404


def test_start_streams_events_in_order(client: TestClient) -> None:
    run_id = create(client, doc(ECHO))["run_id"]
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        assert client.post(f"/api/runs/{run_id}/start").status_code == 202
        events = read_until_finished(ws)
    assert [e["type"] for e in events] == ["step_started", "output", "step_finished", "finished"]
    assert events[1]["text"] == "hi\n"
    assert events[-1]["status"] == "success" and events[-1]["exit_code"] == 0
    history = client.get(f"/api/runs/{run_id}").json()
    assert history["status"] == "success" and history["events"] == events


def test_second_start_conflicts(client: TestClient) -> None:
    run_id = create(client, doc(ECHO))["run_id"]
    assert client.post(f"/api/runs/{run_id}/start").status_code == 202
    assert client.post(f"/api/runs/{run_id}/start").status_code == 409


def test_unknown_id_is_404(client: TestClient) -> None:
    response = client.get("/api/runs/nope")
    assert response.status_code == 404 and response.json()["error"] == "not_found"
    assert client.post("/api/runs/nope/start").status_code == 404
    assert client.post("/api/runs/nope/control", json={"action": "abort"}).status_code == 404
    assert (
        client.post("/api/runs/nope/confirm", json={"step_id": "x", "ok": True}).status_code == 404
    )


def test_invalid_document_is_422(client: TestClient) -> None:
    response = client.post("/api/runs", json={"document": {"schema_version": 1}})
    assert response.status_code == 422 and response.json()["errors"]
    response = client.post(
        "/api/runs", json={"document": doc({"id": "x", "tool": "no-such-tool-xyz"})}
    )
    assert response.status_code == 422 and response.json()["errors"]


def test_decline_over_ws_aborts_without_process(client: TestClient, counter: Path) -> None:
    body = create(client, doc(COPY))
    assert body["needs_confirmation"] is True and body["max_safety"] == "caution"
    run_id = body["run_id"]
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        client.post(f"/api/runs/{run_id}/start")
        request = ws.receive_json()
        assert request["type"] == "confirm_request" and request["step_id"] == "c"
        ws.send_json({"type": "confirm", "step_id": "c", "ok": False})
        events = read_until_finished(ws)
    assert events[-1]["status"] == "aborted"
    assert not counter.exists()


def test_accept_over_rest_runs(client: TestClient, counter: Path) -> None:
    run_id = create(client, doc(COPY))["run_id"]
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        client.post(f"/api/runs/{run_id}/start")
        assert ws.receive_json()["type"] == "confirm_request"
        assert (
            client.post(
                f"/api/runs/{run_id}/confirm", json={"step_id": "c", "ok": True}
            ).status_code
            == 204
        )
        assert read_until_finished(ws)[-1]["status"] == "success"
    assert counter.read_text() == "run\n"


def test_abort_stops_sleeping_step(client: TestClient) -> None:
    run_id = create(client, doc(NAP))["run_id"]
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        client.post(f"/api/runs/{run_id}/start")
        assert ws.receive_json()["type"] == "step_started"
        begin = time.monotonic()
        assert (
            client.post(f"/api/runs/{run_id}/control", json={"action": "abort"}).status_code == 204
        )
        assert read_until_finished(ws)[-1]["status"] == "aborted"
    assert time.monotonic() - begin < 3


def test_dry_run_creates_no_folder(client: TestClient, tmp_path: Path) -> None:
    for _ in range(3):
        create(client, doc(ECHO), dry_run=True)
    assert not (tmp_path / "config" / "whattheshell" / "runs").exists()


def test_folder_created_on_start(client: TestClient) -> None:
    body = create(client, doc(ECHO))
    assert not Path(body["cwd"]).exists()
    client.post(f"/api/runs/{body['run_id']}/start")
    assert Path(body["cwd"]).is_dir()


def test_cwd_must_be_absolute_and_is_returned_resolved(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/runs", json={"document": doc(ECHO), "cwd": "rel"})
    assert response.status_code == 422 and response.json()["error"] == "invalid_cwd"
    assert create(client, doc(ECHO), cwd=str(tmp_path / "." / "bin"))["cwd"] == str(
        tmp_path / "bin"
    )
    assert client.post("/api/runs", json={"document": doc(ECHO), "extra": 1}).status_code == 422


def test_created_runs_are_limited(client: TestClient) -> None:
    ids = [create(client, doc(ECHO))["run_id"] for _ in range(21)]
    assert client.get(f"/api/runs/{ids[0]}").status_code == 404
    assert client.get(f"/api/runs/{ids[1]}").status_code == 200


def test_running_runs_are_limited(client: TestClient) -> None:
    ids = [create(client, doc(NAP))["run_id"] for _ in range(5)]
    for run_id in ids[:4]:
        assert client.post(f"/api/runs/{run_id}/start").status_code == 202
    response = client.post(f"/api/runs/{ids[4]}/start")
    assert response.status_code == 429 and response.json()["error"] == "too_many_runs"
    for run_id in ids[:4]:
        client.post(f"/api/runs/{run_id}/control", json={"action": "abort"})


def test_bad_ws_messages_get_error_and_connection_stays(client: TestClient) -> None:
    run_id = create(client, doc(COPY))["run_id"]
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        for bad in (
            "not json",
            '{"type": "nope"}',
            '{"type": "confirm", "step_id": "zz", "ok": true}',
        ):
            ws.send_text(bad)
            assert ws.receive_json()["type"] == "error"
        client.post(f"/api/runs/{run_id}/start")
        assert ws.receive_json()["type"] == "confirm_request"
        ws.send_json({"type": "confirm", "step_id": "c", "ok": False})
        assert read_until_finished(ws)[-1]["status"] == "aborted"


def test_pause_blocks_next_step_until_resume(client: TestClient) -> None:
    run_id = create(client, doc(*SHORT))["run_id"]
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        client.post(f"/api/runs/{run_id}/start")
        assert ws.receive_json()["step_id"] == "s1"
        client.post(f"/api/runs/{run_id}/control", json={"action": "pause"})
        time.sleep(1)
        events = client.get(f"/api/runs/{run_id}").json()["events"]
        assert [e["step_id"] for e in events if e["type"] == "step_started"] == ["s1"]
        client.post(f"/api/runs/{run_id}/control", json={"action": "resume"})
        events = read_until_finished(ws)
    assert "s2" in [e.get("step_id") for e in events if e["type"] == "step_started"]
