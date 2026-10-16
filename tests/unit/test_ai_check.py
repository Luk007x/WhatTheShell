# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import shutil
import stat
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from whattheshell.ai.check import CheckResult, agents_found, check
from whattheshell.settings import Settings

KEY = "sk-geheim-123"


@pytest.fixture
def models_server() -> Iterator[str]:
    """`GET /v1/models` with two models."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = {"data": [{"id": "llama3:latest"}, {"id": "qwen2.5:7b"}, {"id": "x\x1b[31m"}]}
            self.send_response(200 if self.path == "/v1/models" else 404)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args: Any) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()
    httpd.server_close()


def _settings(**ai: Any) -> Settings:
    return Settings.model_validate({"ai": {"enabled": True, **ai}})


def _items(result: CheckResult) -> dict[str, tuple[bool, str, str]]:
    return {i.name: (i.ok, i.detail, i.hint) for i in result.items}


def test_off_reports_without_provider_import() -> None:
    code = (
        "import sys; from whattheshell.ai.check import check; from whattheshell.settings import "
        "Settings; r = check(Settings()); assert not r.ok and r.items[0].name == 'KI aus', r;"
        "assert not [m for m in sys.modules if m.startswith('whattheshell.ai.providers')]"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603


def test_local_model_with_tag_and_missing(models_server: str) -> None:
    result = check(_settings(local={"base_url": models_server, "model": "llama3"}))
    assert result.ok and _items(result)["Modell verfügbar"][0]
    result = check(_settings(local={"base_url": models_server, "model": "mistral"}))
    ok, detail, hint = _items(result)["Modell verfügbar"]
    assert not result.ok and not ok and "qwen2.5:7b" in detail and hint.endswith("pull mistral`")
    assert "\x1b" not in detail and "x [31m" in detail  # foreign ids made printable


def test_local_unreachable_and_without_network() -> None:
    settings = _settings(local={"base_url": "http://127.0.0.1:1/v1", "model": "llama3"})
    ok, _, hint = _items(check(settings))["Endpunkt"]
    assert not ok and "ollama serve" in hint
    assert check(settings, probe_network=False).ok
    empty = _items(check(_settings(), probe_network=False))["Modell eingetragen"]
    assert not empty[0] and "local.model" in empty[2]


def test_api_key_never_shown(monkeypatch: pytest.MonkeyPatch, models_server: str) -> None:
    monkeypatch.delenv("WTS_TEST_KEY", raising=False)
    api = {"kind": "anthropic", "model": "m", "key_env": "WTS_TEST_KEY"}
    result = check(_settings(provider="api", api=api))
    assert not result.ok and "WTS_TEST_KEY nicht gesetzt" in _items(result)["Schlüssel"][1]
    monkeypatch.setenv("WTS_TEST_KEY", KEY)
    result = check(_settings(provider="api", api=api))
    assert result.ok and KEY not in str(result)
    assert "ersten Aufruf" in _items(result)["Verbindung"][2]
    openai = {**api, "kind": "openai", "base_url": models_server, "model": "qwen2.5:7b"}
    result = check(_settings(provider="api", api=openai))
    assert result.ok and _items(result)["Endpunkt"][0] and KEY not in str(result)


def _script(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", f"{directory}:/usr/bin:/bin")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return directory


# Logged in = the login file reached the throwaway HOME, as in a real call.
_AGENT = 'case "$1" in --version) echo "9.9.9 (Fake)";; auth|login) [ -f "$HOME/{file}" ];; esac\n'


@pytest.mark.parametrize(
    ("kind", "file", "login"),
    [("claude", ".claude/.credentials.json", "claude login"), ("codex", ".codex/auth.json",
     "codex login")],
)  # fmt: skip
def test_agent_program_version_login(
    bin_dir: Path, tmp_path: Path, kind: str, file: str, login: str
) -> None:
    settings = _settings(provider="agent", agent={"kind": kind})
    ok, _, hint = _items(check(settings))["Programm"]
    assert not ok and "npm install -g" in hint
    _script(bin_dir, kind, _AGENT.format(file=file))
    result = check(settings)
    items = _items(result)
    assert items["Version"][:2] == (True, "9.9.9 (Fake)")
    assert not items["Anmeldung"][0] and login in items["Anmeldung"][2]
    (tmp_path / "home" / file).parent.mkdir(parents=True)
    (tmp_path / "home" / file).write_text("{}")
    assert check(settings).ok


def test_agent_timeout_is_an_item(bin_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from whattheshell.ai import check as check_module

    monkeypatch.setattr(check_module, "_AGENT_TIMEOUT", 0.3)
    _script(bin_dir, "claude", "sleep 5\n")
    items = _items(check(_settings(provider="agent")))
    assert not items["Version"][0] and "Zeitlimit" in items["Anmeldung"][1]


def test_keyring_error_is_an_item(monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    fake = types.ModuleType("keyring")

    def broken(service: str, name: str) -> str:
        raise RuntimeError("kaputt")

    fake.get_password = broken  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "keyring", fake)
    api = {"kind": "anthropic", "model": "m", "key_source": "keyring"}
    ok, detail, _ = _items(check(_settings(provider="api", api=api)))["Schlüssel"]
    assert not ok and "Schlüsselbund nicht lesbar" in detail


def test_effective_command_line_shown(bin_dir: Path) -> None:
    _script(bin_dir, "codex", "exit 0\n")
    agent = {"kind": "codex", "model": "gpt-x", "reasoning": "high"}
    detail = _items(check(_settings(provider="agent", agent=agent)))["Aufrufzeile"][1]
    assert detail.startswith("codex exec --sandbox read-only") and "-m gpt-x" in detail
    assert "model_reasoning_effort" in detail


def test_unreadable_login_file(bin_dir: Path, tmp_path: Path) -> None:
    _script(bin_dir, "claude", "exit 0\n")
    login = tmp_path / "home/.claude/.credentials.json"
    login.parent.mkdir(parents=True)
    login.write_text("{}")
    login.chmod(0)
    ok, detail, hint = _items(check(_settings(provider="agent")))["Anmeldung"]
    assert not ok and "Anmeldedatei nicht kopierbar" in detail and ".credentials.json" in hint


def test_agents_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
    assert agents_found() == {"claude": None, "codex": "/usr/bin/codex"}
