# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import shutil
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whattheshell.api import rest
from whattheshell.api.app import create_app
from whattheshell.api.security import Session
from whattheshell.bundled import MODULES_DIR
from whattheshell.catalog import Catalog
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.sandbox import SandboxStatus, self_test

PORT = 48124
DEMO = """#!/bin/sh
echo "Usage: demo [-a] [-b N]"
echo
echo "  -a  flag"
echo "  -b N  number"
"""
DEMO_MODULE = """schema_version: 1
tool: demo
display_name: Demo Werkzeug
category: Test
summary: Nur ein Test
safety: caution
"""
UNAVAILABLE = SandboxStatus(False, "bwrap fehlt", "sudo dnf install bubblewrap", None)
STATUS = self_test()
needs_sandbox = pytest.mark.skipif(
    not STATUS.available or shutil.which("wc") is None, reason="Sandbox oder wc fehlt"
)
WORKFLOW = {
    "schema_version": 1,
    "name": "Zeilen zählen",
    "steps": [{"id": "zaehle", "tool": "wc", "args": {"lines": True}}],
}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "demo").write_text(DEMO)
    (bin_dir / "demo").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "demo.module.yaml").write_text(DEMO_MODULE)
    (modules / "broken.module.yaml").write_text("tool: [")
    registry = ModuleRegistry([MODULES_DIR, modules])
    registry.scan()
    app = create_app(
        Session(port=PORT, token="t"),
        catalog=Catalog(tmp_path / "catalog", registry),
        registry=registry,
        static_dir=tmp_path / "static",
    )
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}", headers={"X-WTS-Token": "t"})


def test_status(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[int] = []

    def fake_self_test() -> SandboxStatus:
        calls.append(1)
        return UNAVAILABLE

    monkeypatch.setattr(rest, "self_test", fake_self_test)
    body = client.get("/api/status").json()
    assert body["app"] == "WhatTheShell"
    assert body["sandbox"]["available"] is False
    assert body["sandbox"]["install_hint"] == "sudo dnf install bubblewrap"
    assert [e["path"] for e in body["module_errors"]] == [
        str(tmp_path / "modules/broken.module.yaml")
    ]
    assert body["workflows_dir"] == str(tmp_path / "config/whattheshell/workflows")
    client.get("/api/status")
    assert calls == [1]  # cached
    assert client.post("/api/sandbox/selftest").status_code == 200
    assert calls == [1, 1]


def test_tools_search(client: TestClient) -> None:
    found = client.get("/api/tools", params={"search": "DEMO"}).json()
    demo = next(t for t in found if t["name"] == "demo")
    assert demo["display_name"] == "Demo Werkzeug"
    assert demo["safety"] == "caution"
    by_display = client.get("/api/tools", params={"search": "werkzeug"}).json()
    assert [t["name"] for t in by_display] == ["demo"]
    assert len(client.get("/api/tools").json()) > 1


def test_tools_list_marks_interactive(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "bin" / "vim").write_text("#!/bin/sh\n")
    (tmp_path / "bin" / "vim").chmod(0o755)
    by_name = {t["name"]: t for t in client.get("/api/tools").json()}
    assert by_name["vim"]["interactive"] is True
    assert by_name["demo"]["interactive"] is False


def test_tool_detail(client: TestClient) -> None:
    body = client.get("/api/tools/demo").json()
    assert body["name"] == "demo"
    assert {o["flags"][0] for o in body["command"]["options"]} == {"-a", "-b"}
    missing = client.get("/api/tools/no-such-tool-xyz")
    assert missing.status_code == 404
    assert missing.json()["error"] == "tool_not_found"
    assert client.get("/api/tools/demo", params={"deep": 2}).status_code == 422


def test_command(client: TestClient) -> None:
    info = client.get("/api/tools/demo").json()
    option = next(o for o in info["command"]["options"] if o["flags"][0] == "-a")
    body = client.post(
        "/api/command",
        json={"tool": "demo", "args": {option["id"]: True}, "extra_args": ["x y"]},
    ).json()
    assert body["argv"][1:] == ["-a", "x y"]
    assert body["display"].endswith("-a 'x y'")
    assert body["safety"] == "caution"
    bad = client.post("/api/command", json={"tool": "demo", "args": {"nope": 1}})
    assert bad.status_code == 422
    assert "nope" in bad.json()["message"]
    assert client.post("/api/command", json={"tool": "no-such-tool-xyz"}).status_code == 404


def test_preview_without_sandbox(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rest, "self_test", lambda: UNAVAILABLE)
    response = client.post("/api/preview", json={"tool": "demo"})
    assert response.status_code == 409
    assert response.json()["install_hint"] == "sudo dnf install bubblewrap"


@needs_sandbox
def test_preview_runs_in_sandbox(client: TestClient) -> None:
    body = client.post(
        "/api/preview", json={"tool": "wc", "args": {"lines": True}, "stdin": "a\nb\n"}
    ).json()
    assert body["stdout"].strip() == "2"
    assert body["exit_code"] == 0
    assert body["timed_out"] is False
    example = client.post(
        "/api/preview",
        json={"tool": "wc", "args": {"lines": True, "file": ["liste.txt"]}, "example": 0},
    ).json()
    assert example["exit_code"] == 0
    assert example["stdout"].split()[0] == "3"
    assert client.post("/api/preview", json={"tool": "wc", "example": 99}).status_code == 422


def test_modules(client: TestClient, tmp_path: Path) -> None:
    body = client.get("/api/modules").json()
    assert body["search_paths"][1] == {"dir": str(tmp_path / "modules"), "count": 1, "exists": True}
    assert any(m["tool"] == "demo" and m["priority"] == 1 for m in body["modules"])
    assert len(body["errors"]) == 1


def test_workflows(client: TestClient, tmp_path: Path) -> None:
    listed = client.get("/api/workflows").json()
    bundled_entry = next(w for w in listed if w["id"] == "log_errors")
    assert bundled_entry["source"] == "bundled"
    got = client.get("/api/workflows/log_errors").json()
    assert got["document"]["name"] == bundled_entry["name"]
    assert "schema_version: 1" in got["raw"]

    saved = client.put("/api/workflows/mein-flow", json={"document": WORKFLOW})
    assert saved.status_code == 200
    target = tmp_path / "config/whattheshell/workflows/mein-flow.workflow.yaml"
    assert saved.json() == {"id": "mein-flow", "path": str(target)}
    assert target.read_text(encoding="utf-8").startswith("schema_version: 1\nname: Zeilen zählen\n")
    again = client.get("/api/workflows/mein-flow").json()
    assert again["document"]["steps"][0]["tool"] == "wc"
    assert {w["id"]: w["source"] for w in client.get("/api/workflows").json()}[
        "mein-flow"
    ] == "user"

    assert client.delete("/api/workflows/mein-flow").status_code == 204
    assert not target.exists()
    assert client.delete("/api/workflows/mein-flow").status_code == 404


def test_workflow_rejections(client: TestClient) -> None:
    invalid: dict[str, Any] = {**WORKFLOW, "steps": [{"id": "a", "tool": "wc", "bogus": 1}]}
    response = client.put("/api/workflows/kaputt", json={"document": invalid})
    assert response.status_code == 422
    errors = response.json()["errors"]
    assert errors
    assert "bogus" in errors[0]["path"]
    assert client.delete("/api/workflows/log_errors").status_code == 403
    for bad_id in ("Gross", "-x", "a.b"):
        assert (
            client.put(f"/api/workflows/{bad_id}", json={"document": WORKFLOW}).status_code == 400
        )
    assert client.get("/api/workflows/gibt-es-nicht").status_code == 404


def test_workflow_validate(client: TestClient) -> None:
    ok = client.post("/api/workflows/validate", json={"document": WORKFLOW}).json()
    assert ok == {"ok": True, "errors": []}
    bad = client.post("/api/workflows/validate", json={"document": {"name": "x"}}).json()
    assert bad["ok"] is False
    assert bad["errors"]


def test_user_file_shadows_bundled(client: TestClient, tmp_path: Path) -> None:
    assert client.put("/api/workflows/log_errors", json={"document": WORKFLOW}).status_code == 200
    shadow = client.get("/api/workflows/log_errors").json()
    assert shadow["document"]["name"] == "Zeilen zählen"
    assert str(tmp_path / "config") in shadow["path"]
    entry = next(w for w in client.get("/api/workflows").json() if w["id"] == "log_errors")
    assert entry["source"] == "user"
    assert client.delete("/api/workflows/log_errors").status_code == 204
    again = client.get("/api/workflows/log_errors").json()
    assert again["document"]["name"] != "Zeilen zählen"  # bundled file is back and untouched


def test_sub_words_are_validated_without_starting_a_process(
    client: TestClient, tmp_path: Path
) -> None:
    marker = tmp_path / "ran"
    script = tmp_path / "bin" / "counter"
    script.write_text(f'#!/bin/sh\necho "$@" >> {marker}\necho "Usage: counter"\n')
    script.chmod(0o755)
    for sub in ("-c/x", "a%00b", "a/-c", "x;id", "1abc"):
        assert client.get(f"/api/tools/counter?sub={sub}").status_code == 422
    assert client.get("/api/tools/-c").status_code == 422
    assert client.get("/api/tools/a%2Fb").status_code in (404, 422)
    bad = {"tool": "counter", "command": ["-c", "id>x"]}
    assert client.post("/api/command", json=bad).status_code == 422
    assert client.post("/api/command", json={"tool": "/bin/sh"}).status_code == 422
    assert not marker.exists()
    # unknown (but well-formed) subcommand: fallback entry, still no help call for it
    body = client.get("/api/tools/counter?sub=unknown").json()
    assert body["source"] == "fallback"
    assert "unknown" not in marker.read_text()  # only the parent's own help was read


def test_preview_busy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rest, "self_test", lambda: STATUS if STATUS.available else UNAVAILABLE)
    if not STATUS.available:
        pytest.skip("Sandbox fehlt")
    monkeypatch.setattr(rest, "PREVIEW_SLOTS", threading.Semaphore(0))
    monkeypatch.setattr(rest, "PREVIEW_WAIT", 0.05)
    assert client.post("/api/preview", json={"tool": "demo"}).status_code == 429


def test_lang_en_translates_tool_and_list(client: TestClient) -> None:
    de = client.get("/api/tools/grep").json()["command"]
    en = client.get("/api/tools/grep", params={"lang": "en"}).json()["command"]
    assert de["display_name"] == "grep – Text durchsuchen"
    assert en["display_name"] == "grep – search text"
    labels = {o["id"]: o["label"] for o in en["options"]}
    assert labels["ignore_case"] == "Ignore case"
    assert labels["word_regexp"] == "Nur ganze Wörter"  # no translation: original stays
    entry = next(
        t for t in client.get("/api/tools", params={"lang": "en"}).json() if t["name"] == "grep"
    )
    assert entry["display_name"] == "grep – search text"
    assert client.get("/api/tools/grep", params={"lang": "../x"}).status_code == 422


def test_workflow_index_fields_and_run_shortcut(client: TestClient, tmp_path: Path) -> None:
    client.put("/api/workflows/log_errors", json={"document": WORKFLOW})
    entry = next(w for w in client.get("/api/workflows").json() if w["id"] == "log_errors")
    assert entry["shadows"] == ["bundled"]
    assert entry["steps"] == 1
    assert entry["error"] is None
    assert "variables" in entry
    assert client.get("/api/status").json()["workflows_watch"] in (True, False)
    plan = client.post("/api/workflows/log_errors/run", json={"dry_run": True})
    assert plan.status_code == 200
    assert "wc" in plan.json()["plan"]
    assert client.post("/api/workflows/gibt-es-nicht/run", json={}).status_code == 404


def test_broken_workflow_is_listed_with_error(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "config/whattheshell/workflows"
    folder.mkdir(parents=True)
    (folder / "kaputt.workflow.yaml").write_text("name: [")
    client.put("/api/workflows/anderer", json={"document": WORKFLOW})  # reload rescans
    entry = next(w for w in client.get("/api/workflows").json() if w["id"] == "kaputt")
    assert "kaputt.workflow.yaml" in entry["error"]


def test_project_file_makes_put_and_delete_conflict(client: TestClient, tmp_path: Path) -> None:
    index = client.app.state.workflows  # type: ignore[attr-defined]
    folder = tmp_path / "proj/.whattheshell/workflows"
    folder.mkdir(parents=True)
    (folder / "pflicht.workflow.yaml").write_text(
        "schema_version: 1\nname: P\nsteps:\n  - { id: a, tool: wc }\n"
    )
    index.dirs[:] = [*index.dirs[:2], folder.resolve()]  # bundled, user, project
    index.scan()
    listed = {w["id"]: w for w in client.get("/api/workflows").json()}
    assert listed["pflicht"]["source"] == "project" and listed["pflicht"]["writable"] is False
    assert listed["log_errors"]["writable"] is True
    for response in (
        client.put("/api/workflows/pflicht", json={"document": WORKFLOW}),
        client.delete("/api/workflows/pflicht"),
    ):
        assert response.status_code == 409
        body = response.json()
        assert body["error"] == "shadowed" and str(folder) in body["message"]
