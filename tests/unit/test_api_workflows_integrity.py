# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

from fastapi.testclient import TestClient

from .test_api_rest import WORKFLOW, client  # noqa: F401

TEXT = "schema_version: 1\nname: Neu\nsteps:\n  - { id: a, tool: wc }\n"
IMPORT = "/api/workflows/import"


def _item(api: TestClient, workflow_id: str) -> dict[str, object]:
    return next(w for w in api.get("/api/workflows").json() if w["id"] == workflow_id)


def test_list_and_get_carry_integrity(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    assert _item(client, "log_errors")["integrity"] == "ok"
    client.put("/api/workflows/mein-flow", json={"document": WORKFLOW})  # save stamps
    assert _item(client, "mein-flow")["integrity"] == "ok"
    got = client.get("/api/workflows/mein-flow").json()
    assert got["source"] == "user" and got["integrity"] == "ok" and got["error"] is None
    folder = tmp_path / "config/whattheshell/workflows"
    (folder / "mein-flow.workflow.yaml").write_text(TEXT)
    client.put("/api/workflows/anderer", json={"document": WORKFLOW})  # rescan
    assert _item(client, "mein-flow")["integrity"] == "modified"
    (folder / "kaputt.workflow.yaml").write_text("name: [")
    client.put("/api/workflows/anderer", json={"document": WORKFLOW})
    broken = _item(client, "kaputt")
    assert broken["integrity"] == "invalid" and broken["error"]


def test_import_ok_duplicate_overwrite(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    first = client.post(IMPORT, json={"filename": "neu.workflow.yaml", "content": TEXT})
    assert first.status_code == 201
    assert first.json()["source"] == "user" and first.json()["integrity"] == "ok"
    target = tmp_path / "config/whattheshell/workflows/neu.workflow.yaml"
    assert target.read_text() == TEXT
    dup = client.post(IMPORT, json={"filename": "neu.workflow.yaml", "content": TEXT})
    assert dup.status_code == 409 and dup.json()["error"] == "exists"
    over = client.post(
        IMPORT, json={"filename": "neu.workflow.yaml", "content": TEXT, "overwrite": True}
    )
    assert over.status_code == 201


def test_import_rejections(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    bad = client.post(IMPORT, json={"filename": "x.workflow.yaml", "content": "name: ["})
    assert bad.status_code == 422 and bad.json()["errors"]
    assert not (tmp_path / "config/whattheshell/workflows/x.workflow.yaml").exists()
    for name in ("../x.workflow.yaml", "a/b.workflow.yaml", "X.workflow.yaml", "x.yaml"):
        response = client.post(IMPORT, json={"filename": name, "content": TEXT})
        assert response.status_code == 400, name
    huge = client.post(
        IMPORT, json={"filename": "big.workflow.yaml", "content": TEXT + "#" * 1_100_000}
    )
    assert huge.status_code == 413


def test_run_refused_until_accepted(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    client.put("/api/workflows/mein-flow", json={"document": WORKFLOW})
    path = tmp_path / "config/whattheshell/workflows/mein-flow.workflow.yaml"
    path.write_text(TEXT)
    client.put("/api/workflows/anderer", json={"document": WORKFLOW})  # rescan
    refused = client.post("/api/workflows/mein-flow/run", json={})
    assert refused.status_code == 409
    assert refused.json() == {
        "error": "integrity",
        "status": "modified",
        "message": "Datei wurde außerhalb der App geändert. Prüfen und übernehmen.",
    }
    assert client.post("/api/workflows/mein-flow/run", json={"dry_run": True}).status_code == 200
    accepted = client.post("/api/workflows/mein-flow/accept")
    assert accepted.status_code == 200 and accepted.json()["integrity"] == "ok"
    created = client.post("/api/workflows/mein-flow/run", json={})
    assert created.status_code == 200
    started = client.post(f"/api/runs/{created.json()['run_id']}/start")
    assert started.status_code == 202


def test_accept_invalid_and_unknown(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    folder = tmp_path / "config/whattheshell/workflows"
    folder.mkdir(parents=True)
    (folder / "kaputt.workflow.yaml").write_text("name: [")
    client.put("/api/workflows/anderer", json={"document": WORKFLOW})
    assert client.post("/api/workflows/kaputt/accept").status_code == 422
    assert client.post("/api/workflows/gibt-es-nicht/accept").status_code == 404
    assert client.post("/api/workflows/log_errors/accept").json()["integrity"] == "ok"


def test_import_lone_surrogate_is_422(client: TestClient) -> None:  # noqa: F811
    response = client.post(
        IMPORT,
        content=b'{"filename": "s.workflow.yaml", "content": "\\ud800"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422 and response.json()["error"] == "encoding"
