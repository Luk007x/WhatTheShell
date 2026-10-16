# SPDX-License-Identifier: AGPL-3.0-or-later
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from whattheshell import i18n
from whattheshell.api.security import SecurityMiddleware, Session
from whattheshell.i18n import _, current_lang, normalize, resolve_default, use_lang

from .test_api_security import GOOD_ORIGIN, PORT, TOKEN, client  # noqa: F401


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    for name in ("WTS_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setitem(i18n.CATALOGS["en"], "Hallo {name}", "Hello {name}")
    monkeypatch.setitem(i18n.CATALOGS["en"], "Probe", "Probe-en")


def test_translate_fallback_and_braces() -> None:
    with use_lang("en"):
        assert _("Hallo {name}", name="x") == "Hello x"
        assert _("Unbekannt {roh}") == "Unbekannt {roh}"  # no kw: never formatted
        assert _("Unbekannt {{a}} {n}", n=1) == "Unbekannt {a} 1"
    with use_lang("de"):
        assert _("Hallo {name}", name="x") == "Hallo x"


def test_normalize() -> None:
    values = ("de", "de-DE", "en-US", "de_DE.UTF-8", "fr", "", None, "dex")
    assert [normalize(v) for v in values] == ["de", "de", "en", "de", None, None, None, None]


def test_use_lang_restores() -> None:
    before = current_lang()
    with use_lang("de" if before == "en" else "en"):
        assert current_lang() != before
    assert current_lang() == before


def test_default_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert resolve_default() == "en"
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert resolve_default() == "de"
    cfg = tmp_path / "cfg" / "whattheshell"
    cfg.mkdir(parents=True)
    (cfg / "settings.yaml").write_text("schema_version: 1\nlanguage: en\n")
    assert resolve_default() == "en"  # settings beat locale
    monkeypatch.setenv("WTS_LANG", "de")
    assert resolve_default() == "de"  # env beats settings


def test_settings_language_cache_follows_file(tmp_path: Path) -> None:
    path = tmp_path / "cfg" / "whattheshell" / "settings.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("schema_version: 1\nlanguage: de\n")
    assert resolve_default() == "de"
    path.write_text("schema_version: 1\nlanguage: en\n")  # size equal, mtime differs
    os.utime(path, ns=(1, 1))
    assert resolve_default() == "en"


def test_put_settings_takes_effect_immediately(client: TestClient) -> None:  # noqa: F811
    assert resolve_default() == "en"
    body = client.get("/api/settings", headers=TOKEN).json()
    body.pop("key_status"), body.pop("load_error")  # read-only view fields
    body["language"] = "de"
    reply = client.put("/api/settings", json=body, headers={**TOKEN, **GOOD_ORIGIN})
    assert reply.status_code == 200
    assert resolve_default() == "de"


def test_api_language_header() -> None:
    app = FastAPI()  # probe app: the real middleware around one translated route
    app.add_middleware(SecurityMiddleware, session=Session(port=PORT, token="secret-token"))

    @app.get("/api/probe-lang")
    def probe() -> dict[str, str]:
        return {"text": _("Probe")}

    probe_client = TestClient(app, base_url=f"http://127.0.0.1:{PORT}")
    get = lambda **h: probe_client.get("/api/probe-lang", headers={**TOKEN, **h}).json()["text"]  # noqa: E731
    assert get(**{"X-WTS-Lang": "en"}) == "Probe-en"
    assert get(**{"X-WTS-Lang": "de"}) == "Probe"
    assert get(**{"Accept-Language": "en-US,de;q=0.5"}) == "Probe-en"
    assert get(**{"X-WTS-Lang": "de", "Accept-Language": "en"}) == "Probe"
