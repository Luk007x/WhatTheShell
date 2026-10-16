# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whattheshell import i18n
from whattheshell.api import runs as runs_module
from whattheshell.api.runs import router as runs_router

from .test_api_runs import doc
from .test_api_security import PORT, TOKEN, client  # noqa: F401

UNKNOWN = "/api/workflows/no-such-workflow"


@pytest.fixture(autouse=True)
def _config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))


def message(client: TestClient, lang: str) -> str:  # noqa: F811
    response = client.get(UNKNOWN, headers={**TOKEN, "X-WTS-Lang": lang})
    assert response.status_code == 404
    return str(response.json()["message"])


def test_unknown_workflow_in_both_languages(client: TestClient) -> None:  # noqa: F811
    assert message(client, "en") == "Workflow 'no-such-workflow' does not exist."
    assert message(client, "de") == "Workflow 'no-such-workflow' gibt es nicht."


def test_middleware_refusal_follows_language(client: TestClient) -> None:  # noqa: F811
    english = client.get("/api/status", headers={"X-WTS-Lang": "en"}).json()["message"]
    german = client.get("/api/status", headers={"X-WTS-Lang": "de"}).json()["message"]
    assert english.startswith("Token missing") and german.startswith("Token fehlt")


@pytest.mark.parametrize(
    ("lang", "expected"), [("en", "Internal error: boom"), ("de", "Interner Fehler: boom")]
)
def test_run_thread_uses_language_of_starting_request(
    client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    lang: str,
    expected: str,
) -> None:
    def crash(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(runs_module.Runner, "run", crash)
    assert runs_router  # routes are part of the full app
    headers = {**TOKEN, "X-WTS-Lang": lang}
    body = {"document": doc({"id": "a", "tool": "echo"})}
    run_id = client.post("/api/runs", json=body, headers=headers).json()["run_id"]
    assert client.post(f"/api/runs/{run_id}/start", headers=headers).status_code == 202
    info = client.app.state.runs.get(run_id)  # type: ignore[attr-defined]
    assert info.thread is not None
    info.thread.join(5)
    finished = client.get(f"/api/runs/{run_id}", headers=headers).json()["events"][-1]
    assert finished["type"] == "finished" and finished["message"] == expected


def test_no_missing_catalog_entries(
    client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WTS_I18N_DEBUG", "1")
    i18n.missing.clear()
    headers = {**TOKEN, "X-WTS-Lang": "en"}
    client.get("/api/workflows/Bad_ID", headers=headers)
    client.get(UNKNOWN, headers=headers)
    client.get("/api/modules/no-such-module", headers=headers)
    client.delete("/api/modules/no-such-module", headers=headers)
    client.get("/api/runs/none", headers=headers)
    client.post("/api/runs/none/confirm", json={"step_id": "x", "ok": True}, headers=headers)
    client.get("/api/tools/ls?sub=Bad%20Word", headers=headers)
    client.put("/api/workflows/Bad_ID", json={"document": {}}, headers=headers)
    client.get("/api/status", headers={"X-WTS-Lang": "en"})
    client.get("/api/terminal/transcripts/../x", headers=headers)
    client.delete("/api/terminal/transcripts/bad", headers=headers)
    client.delete("/api/terminal/transcripts/missing.txt", headers=headers)
    assert i18n.missing == set()
