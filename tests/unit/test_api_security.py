# SPDX-License-Identifier: AGPL-3.0-or-later
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from whattheshell.api.app import create_app
from whattheshell.api.security import Session
from whattheshell.catalog import Catalog
from whattheshell.modules.registry import ModuleRegistry

PORT = 48123
TOKEN = {"X-WTS-Token": "secret-token"}
GOOD_ORIGIN = {"Origin": f"http://localhost:{PORT}"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>wts</h1>")
    registry = ModuleRegistry([])
    app = create_app(
        Session(port=PORT, token="secret-token"),
        catalog=Catalog(tmp_path / "cache", registry),
        registry=registry,
        static_dir=static,
    )
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}")


def test_session_token_is_random() -> None:
    assert Session(port=1).token != Session(port=1).token
    assert len(Session(port=1).token) >= 43


def test_api_needs_token(client: TestClient) -> None:
    missing = client.get("/api/status")
    assert missing.status_code == 401
    assert missing.json()["error"] == "token"
    assert client.get("/api/status", headers={"X-WTS-Token": "wrong"}).status_code == 401
    assert client.get("/api/status", headers=TOKEN).status_code == 200


def test_host_is_checked_everywhere(client: TestClient) -> None:
    evil = {"Host": f"evil.example:{PORT}"}
    for path in ("/", "/api/status"):
        response = client.get(path, headers={**TOKEN, **evil})
        assert response.status_code == 400
        assert response.json()["error"] == "host"
    assert client.get("/", headers={"Host": f"127.0.0.1:{PORT + 1}"}).status_code == 400
    assert (
        client.get("/api/status", headers={**TOKEN, "Host": f"localhost:{PORT}"}).status_code == 200
    )


def test_origin_is_checked_for_unsafe_methods(client: TestClient) -> None:
    foreign = client.post(
        "/api/sandbox/selftest", headers={**TOKEN, "Origin": "http://evil.example"}
    )
    assert foreign.status_code == 403
    assert foreign.json()["error"] == "origin"
    assert (
        client.post(
            "/api/command", headers={**TOKEN, "Origin": "http://evil.example"}, json={}
        ).status_code
        == 403
    )
    # GET is not guarded by Origin; correct and absent Origin pass the check (422: empty body)
    assert (
        client.get("/api/status", headers={**TOKEN, "Origin": "http://evil.example"}).status_code
        == 200
    )
    for headers in ({**TOKEN, **GOOD_ORIGIN}, TOKEN):
        assert client.post("/api/command", headers=headers, json={}).status_code == 422


def test_static_needs_no_token_and_no_cors(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "<h1>wts</h1>" in response.text
    for answer in (response, client.get("/api/status", headers={**TOKEN, **GOOD_ORIGIN})):
        assert not [h for h in answer.headers if h.lower().startswith("access-control-")]


def test_no_docs_endpoints(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path, headers=TOKEN).status_code == 404


def test_missing_frontend_gives_503(tmp_path: Path) -> None:
    registry = ModuleRegistry([])
    app = create_app(
        Session(port=PORT),
        catalog=Catalog(tmp_path / "cache", registry),
        registry=registry,
        static_dir=tmp_path / "nothing",
    )
    response = TestClient(app, base_url=f"http://127.0.0.1:{PORT}").get("/")
    assert response.status_code == 503
    assert "npm run build" in response.json()["message"]


def test_websocket_needs_token_and_origin(client: TestClient) -> None:
    host = {"Host": f"127.0.0.1:{PORT}"}
    for url, headers, code in (
        ("/ws/runs/x", host, 4401),
        ("/ws/runs/x?token=wrong", host, 4401),
        ("/ws/runs/x?token=secret-token", {**host, "Origin": "http://evil.example"}, 4403),
        ("/ws/runs/x?token=secret-token", {"Host": "evil.example"}, 4400),
    ):
        with (
            pytest.raises(WebSocketDisconnect) as err,
            client.websocket_connect(url, headers=headers),
        ):
            pass
        assert err.value.code == code


def test_body_limit(client: TestClient) -> None:
    big = b"x" * (1_048_576 + 1)
    declared = client.post("/api/command", headers=TOKEN, content=big)
    assert declared.status_code == 413
    assert declared.json()["error"] == "body_too_large"

    def chunks() -> Iterator[bytes]:
        yield big[:600_000]
        yield big[600_000:]

    streamed = client.post("/api/command", headers=TOKEN, content=chunks())
    assert streamed.status_code == 413


def test_http_errors_use_common_shape(client: TestClient) -> None:
    missing = client.get("/api/nope", headers=TOKEN)
    assert missing.status_code == 404
    assert set(missing.json()) == {"error", "message"}
    assert missing.json()["error"] == "not_found"
