# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from whattheshell.api.app import create_app
from whattheshell.api.security import Session
from whattheshell.bundled import MODULES_DIR
from whattheshell.catalog import Catalog
from whattheshell.modules.registry import ModuleRegistry

PORT = 48125
DEMO = '#!/bin/sh\necho "Usage: demo [-a]"\necho\necho "  -a  flag"\n'
MODULE = "schema_version: 1\ntool: demo\ndisplay_name: Demo\n"


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


def user_file(tmp_path: Path, tool: str) -> Path:
    return tmp_path / f"config/whattheshell/modules/{tool}.module.yaml"


def test_get_module_bundled_and_missing(client: TestClient) -> None:
    body = client.get("/api/modules/grep").json()
    assert body["source"] == "bundled" and body["scaffold_available"] is True
    assert body["document"]["tool"] == "grep" and "schema_version" in body["raw"]
    assert "override_mode" not in body["document"]  # defaults are left out
    missing = client.get("/api/modules/no-such-tool-xyz")
    assert missing.status_code == 404 and "scaffold" in missing.json()["message"]


def test_put_get_delete_roundtrip(client: TestClient, tmp_path: Path) -> None:
    done = client.put("/api/modules/demo", json={"raw": MODULE})
    assert done.json() == {"tool": "demo", "path": str(user_file(tmp_path, "demo"))}
    assert user_file(tmp_path, "demo").read_text() == MODULE
    assert not list(user_file(tmp_path, "demo").parent.glob("*.tmp"))
    assert client.get("/api/tools/demo").json()["command"]["display_name"] == "Demo"
    assert client.get("/api/modules/demo").json()["source"] == "user"
    assert client.delete("/api/modules/demo").status_code == 204
    assert not user_file(tmp_path, "demo").exists()
    assert client.get("/api/tools/demo").json()["command"]["display_name"] is None


def test_put_rejects_invalid_and_foreign_tool(client: TestClient, tmp_path: Path) -> None:
    bad = client.put("/api/modules/demo", json={"raw": "tool: ["})
    assert bad.status_code == 422
    assert bad.json()["errors"][0]["line"] is not None
    wrong = client.put("/api/modules/demo", json={"raw": MODULE.replace("demo", "other")})
    assert wrong.status_code == 422 and wrong.json()["error"] == "tool_mismatch"
    assert not user_file(tmp_path, "demo").exists()
    assert client.put("/api/modules/..%2Fx", json={"raw": MODULE}).status_code in (404, 422)


def test_delete_bundled_and_unknown(client: TestClient) -> None:
    assert client.delete("/api/modules/grep").status_code == 403
    assert client.delete("/api/modules/no-such-tool-xyz").status_code == 404


def test_scaffold_is_raw_and_validates(client: TestClient) -> None:
    client.put("/api/modules/demo", json={"raw": MODULE})
    raw = client.post("/api/modules/scaffold", json={"tool": "demo"}).json()["raw"]
    assert "tool: demo" in raw and "display_name: demo" in raw  # module override not applied
    assert client.put("/api/modules/demo", json={"raw": raw}).status_code == 200
    assert client.post("/api/modules/scaffold", json={"tool": "nope-xyz"}).status_code == 404
    bad = client.post("/api/modules/scaffold", json={"tool": "demo", "command": ["--x"]})
    assert bad.status_code == 422


def test_templates_of_grep(client: TestClient) -> None:
    [template] = client.get("/api/templates/grep").json()
    assert template["title"] == "Treffer zählen"
    assert template["workflow"]["id"] == "grep_count"
    assert template["workflow"]["document"]["steps"][0]["tool"] == "grep"
    assert client.get("/api/templates/demo").json() == []


def test_template_with_broken_workflow_reports_error(client: TestClient, tmp_path: Path) -> None:
    raw = MODULE + "templates:\n  - {title: Kaputt, workflow: nope.workflow.yaml}\n"
    client.put("/api/modules/demo", json={"raw": raw})
    [template] = client.get("/api/templates/demo").json()
    assert template["workflow"]["id"] is None and template["error"]


def test_lifespan_starts_and_stops_watcher(client: TestClient, tmp_path: Path) -> None:
    with client:
        deadline = time.monotonic() + 5
        while not client.get("/api/status").json()["modules_watch"] and time.monotonic() < deadline:
            time.sleep(0.05)
        assert client.get("/api/status").json()["modules_watch"] is True
        user_file(tmp_path, "demo").write_text(MODULE)
        registry: ModuleRegistry = client.app.state.registry  # type: ignore[attr-defined]
        while not registry.for_tool("demo") and time.monotonic() < deadline:
            time.sleep(0.05)
        assert registry.for_tool("demo")
    deadline = time.monotonic() + 5
    while any(t.name == "wts-modules-watch" for t in threading.enumerate()):
        assert time.monotonic() < deadline, "watcher thread still running"
        time.sleep(0.05)
