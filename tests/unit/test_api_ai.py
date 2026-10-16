# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, NoReturn

import pytest
from fastapi.testclient import TestClient

from whattheshell.ai.fake import FakeProvider
from whattheshell.api import ai_api
from whattheshell.api.app import create_app
from whattheshell.api.security import Session
from whattheshell.bundled import MODULES_DIR
from whattheshell.catalog import Catalog
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.settings import AiSettings, Settings

PORT = 48126
KEY = "sk-ant-TOPSECRET-1234"
DEMO = '#!/bin/sh\necho "Usage: demo [-a]"\necho\necho "  -a  flag"\n'
MODULE = "schema_version: 1\ntool: demo\ndisplay_name: Demo\n"
WORKFLOW = "schema_version: 1\nname: Mein Test\nsteps:\n  - { id: a, kind: message, text: hi }\n"
BODIES: dict[str, dict[str, Any]] = {
    "improve-module": {"tool": "demo"},
    "examples": {"tool": "demo"},
    "draft-workflow": {"description": "x"},
    "diagnose": {"step": {"command": "demo"}},
    "apply": {"kind": "module", "raw": MODULE, "target_name": "demo.module.yaml"},
}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "demo").write_text(DEMO)
    (bin_dir / "demo").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    user_dir = tmp_path / "config/whattheshell/modules"
    user_dir.mkdir(parents=True)
    registry = ModuleRegistry([MODULES_DIR, user_dir])
    registry.scan()
    app = create_app(
        Session(port=PORT, token="t"),
        catalog=Catalog(tmp_path / "catalog", registry),
        registry=registry,
        static_dir=tmp_path / "static",
    )
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}", headers={"X-WTS-Token": "t"})


@pytest.fixture
def fake(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """AI on, `make_provider` replaced by a FakeProvider."""
    client.app.state.settings = Settings(ai=AiSettings(enabled=True))  # type: ignore[attr-defined]
    provider = FakeProvider([])
    monkeypatch.setattr(ai_api, "make_provider", lambda settings: provider)
    return provider


def _forbidden(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("Netzwerk oder Fremdprozess bei ausgeschalteter KI")


@pytest.mark.parametrize("task", list(BODIES))
def test_disabled_is_403_without_provider_import(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, task: str
) -> None:
    monkeypatch.delitem(sys.modules, "whattheshell.ai.providers", raising=False)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    reply = client.post(
        f"/api/ai/{task}", json={**BODIES[task], "send": True} if task != "apply" else BODIES[task]
    )
    assert reply.status_code == 403 and reply.json()["error"] == "ai_disabled"
    assert "whattheshell.ai.providers" not in sys.modules
    assert client.post(f"/api/ai/{task}", json={"bogus": 1}).status_code == 403  # gate before 422


def test_check_reports_ai_off_with_200_without_provider_import(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delitem(sys.modules, "whattheshell.ai.providers", raising=False)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    reply = client.get("/api/ai/check")
    assert reply.status_code == 200
    body = reply.json()
    assert body["ok"] is False and [i["name"] for i in body["items"]] == ["KI aus"]
    assert "wts ai enable" in body["items"][0]["hint"]
    assert "whattheshell.ai.providers" not in sys.modules


def test_agents_listed_with_ai_off(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/claude" if name == "claude" else None)
    reply = client.get("/api/ai/agents")
    assert reply.status_code == 200
    assert reply.json() == {"claude": "/bin/claude", "codex": None}


def test_check_without_network(client: TestClient, fake: FakeProvider) -> None:
    body = client.get("/api/ai/check", params={"network": 0}).json()
    assert body["provider"] == "local" and body["ok"] is False
    assert {i["name"]: i["ok"] for i in body["items"]} == {
        "Modell eingetragen": False,
        "Endpunkt": True,
    }


def test_preview_sends_nothing_and_masks(
    client: TestClient, fake: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    reply = client.post("/api/ai/draft-workflow", json={"description": f"nutze {KEY}"})
    body = reply.json()
    assert reply.status_code == 200 and fake.prompts == []
    assert KEY not in reply.text and "***" in body["prompt"]["user"]
    assert body["chars"] == len(body["prompt"]["system"]) + len(body["prompt"]["user"])


def test_send_module_valid_writes_nothing(
    client: TestClient, fake: FakeProvider, tmp_path: Path
) -> None:
    fake._responses.append(f"```yaml\n{MODULE}```")
    reply = client.post("/api/ai/improve-module", json={"tool": "demo", "send": True})
    body = reply.json()
    assert reply.status_code == 200 and body["valid"] is True and body["errors"] == []
    assert body["kind"] == "module" and body["target"] == "demo.module.yaml"
    assert body["raw"] == MODULE and "+tool: demo" in body["diff"]
    assert len(fake.prompts) == 1 and "Befehl demo" in fake.prompts[0].system
    assert not (tmp_path / "config/whattheshell/modules/demo.module.yaml").exists()


def test_apply_writes_and_reloads(client: TestClient, fake: FakeProvider, tmp_path: Path) -> None:
    assert client.get("/api/modules/demo").status_code == 404
    reply = client.post("/api/ai/apply", json=BODIES["apply"])
    path = tmp_path / "config/whattheshell/modules/demo.module.yaml"
    assert reply.status_code == 200 and reply.json() == {"path": str(path)}
    assert path.read_text() == MODULE
    assert client.get("/api/modules/demo").json()["source"] == "user"
    reply = client.post(
        "/api/ai/apply",
        json={"kind": "workflow", "raw": WORKFLOW, "target_name": "t.workflow.yaml"},
    )
    assert reply.status_code == 200 and Path(reply.json()["path"]).parent.name == "workflows"


def test_invalid_answer_and_apply_refused(
    client: TestClient, fake: FakeProvider, tmp_path: Path
) -> None:
    fake._responses.append("schema_version: 1\ntool: demo\nbogus: 1\n")
    body = client.post("/api/ai/improve-module", json={"tool": "demo", "send": True}).json()
    assert body["valid"] is False and body["errors"]
    for kind, raw, name in (
        ("module", body["raw"], "demo.module.yaml"),
        ("module", MODULE, "../demo.module.yaml"),
        ("module", MODULE, "other.module.yaml"),
        ("workflow", MODULE, "x.workflow.yaml"),
    ):
        reply = client.post("/api/ai/apply", json={"kind": kind, "raw": raw, "target_name": name})
        assert reply.status_code == 422, name
    assert not list((tmp_path / "config/whattheshell").rglob("*.yaml"))


def test_workflow_target_from_answer(client: TestClient, fake: FakeProvider) -> None:
    fake._responses.append(WORKFLOW)
    body = client.post("/api/ai/draft-workflow", json={"description": "x", "send": True}).json()
    assert (
        body["valid"] and body["kind"] == "workflow" and body["target"] == "mein-test.workflow.yaml"
    )


def test_provider_error_is_502(client: TestClient, fake: FakeProvider) -> None:
    reply = client.post("/api/ai/diagnose", json={"step": {"command": "x"}, "send": True})
    assert reply.status_code == 502 and reply.json()["error"] == "ai_provider"


def test_diagnose_outputs_only_on_request(client: TestClient, fake: FakeProvider) -> None:
    step = {"command": "demo -a", "exit_code": 2, "stdout": "OUT-TEXT", "stderr": "ERR-TEXT"}
    plain = client.post("/api/ai/diagnose", json={"step": step}).json()["prompt"]["user"]
    assert "OUT-TEXT" not in plain and "ERR-TEXT" not in plain and "demo -a" in plain
    full = client.post("/api/ai/diagnose", json={"step": step, "include_output": True})
    assert "OUT-TEXT" in full.json()["prompt"]["user"]
    client.app.state.settings.ai.send_outputs = True  # type: ignore[attr-defined]
    forced = client.post("/api/ai/diagnose", json={"step": step}).json()["prompt"]["user"]
    assert "OUT-TEXT" in forced
    fake._responses.append("Ursache: ...")
    body = client.post("/api/ai/diagnose", json={"step": step, "send": True}).json()
    assert body["kind"] == "text" and body["raw"] == "Ursache: ..." and body["target"] is None


def test_busy_is_429(
    client: TestClient, fake: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_api, "AI_SLOTS", threading.Semaphore(0))
    monkeypatch.setattr(ai_api, "AI_WAIT", 0)
    reply = client.post("/api/ai/diagnose", json={"step": {"command": "x"}, "send": True})
    assert reply.status_code == 429 and fake.prompts == []


def test_provider_error_is_masked(
    client: TestClient, fake: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", KEY)

    def boom(settings: object) -> object:
        raise RuntimeError(f"401 {KEY}")

    monkeypatch.setattr(ai_api, "make_provider", boom)
    reply = client.post("/api/ai/draft-workflow", json={"description": "x", "send": True})
    assert reply.status_code == 502 and KEY not in reply.text and "***" in reply.text
