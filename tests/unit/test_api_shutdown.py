# SPDX-License-Identifier: AGPL-3.0-or-later
# ruff: noqa: F811  (fixtures imported from test_api_terminal)
import time

import pytest
from fastapi.testclient import TestClient

from tests.unit.test_api_terminal import (  # noqa: F401 - fixtures
    TERM,
    FakePty,
    client,
    closed_code,
    connect,
    doc,
    fakes,
    open_terminal,
    start,
    until,
    wait_for,
)
from whattheshell.api.runs import RunManager, run_manager
from whattheshell.api.terminal import TerminalHub, terminal_hub

SLEEP = {"id": "s", "tool": "sleep", "extra_args": ["30"]}


def test_shutdown_endpoint_without_server_is_503(client: TestClient) -> None:
    response = client.post("/api/shutdown")
    assert response.status_code == 503 and response.json()["error"] == "no_server"


def test_shutdown_endpoint_calls_registered_callable(client: TestClient) -> None:
    calls: list[int] = []
    client.app.state.request_shutdown = lambda: calls.append(1)  # type: ignore[attr-defined]
    response = client.post("/api/shutdown")
    assert response.status_code == 202 and response.json() == {"status": "stopping"}
    assert calls == [1]


def test_shutdown_endpoint_needs_token(client: TestClient) -> None:
    client.app.state.request_shutdown = lambda: pytest.fail("must not run")  # type: ignore[attr-defined]
    assert client.post("/api/shutdown", headers={"X-WTS-Token": "wrong"}).status_code == 401


def test_run_manager_shutdown_aborts_running_run(client: TestClient) -> None:
    run_id = start(client, doc(SLEEP))
    manager = run_manager(client.app)  # type: ignore[arg-type]
    info = manager.get(run_id)
    assert info is not None and info.thread is not None
    wait_for(lambda: info.status == "running" and bool(info.events))
    started = time.monotonic()
    manager.shutdown()
    manager.shutdown()  # idempotent
    assert not info.thread.is_alive() and time.monotonic() - started < 5
    assert info.status == "aborted"


def test_terminal_hub_shutdown_closes_with_1001(client: TestClient, fakes: list[FakePty]) -> None:
    run_id = start(client, doc(TERM))
    with connect(client, f"/ws/runs/{run_id}") as run_ws:
        until(run_ws, "terminal_request")
        with open_terminal(client, run_id) as ws:
            ws.send_json({"type": "open", "cols": 80, "rows": 24})
            wait_for(lambda: len(fakes) == 1)
            hub = terminal_hub(client.app)  # type: ignore[arg-type]
            hub.shutdown()
            hub.shutdown()  # idempotent
            assert closed_code(ws)[0] == 1001
        assert fakes[0].code == -1  # terminate ran
        until(run_ws, "finished")


def test_lifespan_exit_calls_shutdowns(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    monkeypatch.setattr(
        TerminalHub, "shutdown", lambda self, timeout=5.0: order.append("terminals")
    )
    monkeypatch.setattr(RunManager, "shutdown", lambda self, timeout=5.0: order.append("runs"))
    with client:
        assert order == []
    assert order == ["terminals", "runs"]
