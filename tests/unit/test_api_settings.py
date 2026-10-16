# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from whattheshell.api.app import create_app
from whattheshell.api.security import Session
from whattheshell.settings import load_settings, settings_path

from .test_api_ai import KEY, PORT, client  # noqa: F401


def test_get_defaults_and_key_status(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    body = client.get("/api/settings").json()
    assert body["ai"]["enabled"] is False and body["key_status"] == "missing"
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    reply = client.get("/api/settings")
    assert reply.json()["key_status"] == "set" and KEY not in reply.text


def test_put_saves_and_reloads(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    document = client.get("/api/settings").json()
    document.pop("load_error")
    document.pop("key_status")  # read-only, not part of the document
    document["ai"]["enabled"] = True
    document["ai"]["provider"] = "api"
    reply = client.put("/api/settings", json=document)
    assert reply.status_code == 200 and reply.json()["ai"]["provider"] == "api"
    assert client.get("/api/settings").json()["ai"]["enabled"] is True
    assert load_settings().ai.enabled and settings_path().stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "patch",
    [
        {"provider": "nope"},
        {"api": {"api_key": KEY}},
        {"api": {"key_env": KEY}},
    ],
)
def test_put_invalid_is_422_and_leaks_no_key(client: TestClient, patch: dict[str, object]) -> None:  # noqa: F811
    reply = client.put("/api/settings", json={"schema_version": 1, "ai": patch})
    assert reply.status_code == 422 and reply.json()["error"] == "validation"
    assert KEY not in reply.text and not settings_path().exists()


def test_broken_file_reports_load_error(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    assert client.get("/api/settings").json()["load_error"] is None
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text("schema_version: 1\nai:\n  agent:\n    command: [claude]\n")
    app = create_app(
        Session(port=PORT, token="t"),
        catalog=client.app.state.catalog,  # type: ignore[attr-defined]
        registry=client.app.state.registry,  # type: ignore[attr-defined]
        static_dir=tmp_path / "static",
    )
    broken = TestClient(app, base_url=f"http://127.0.0.1:{PORT}", headers={"X-WTS-Token": "t"})
    body = broken.get("/api/settings").json()
    assert "ai.agent.command" in body["load_error"] and body["ai"]["enabled"] is False
