# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import stat
import sys
import threading
import types
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from whattheshell.ai.protocol import Prompt
from whattheshell.ai.providers import build
from whattheshell.ai.providers.agent_cli import AgentCliProvider
from whattheshell.ai.providers.anthropic import AnthropicProvider
from whattheshell.ai.providers.keys import resolve_key
from whattheshell.ai.providers.openai_compat import OpenAICompatProvider
from whattheshell.settings import AiSettings, ApiSettings

PROMPT = Prompt(system="SYS", user="USER", max_tokens=50)
SECRET = "sk-geheim-123"


class _Server:
    def __init__(self) -> None:
        self.seen: list[tuple[str, dict[str, str], Any]] = []
        self.status = 200
        self.reply: Any = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                outer.seen.append(
                    (self.path, {k.lower(): v for k, v in self.headers.items()}, json.loads(raw))
                )
                self.send_response(outer.status)
                if outer.status == 302:
                    self.send_header("Location", "http://127.0.0.1:1/x")
                self.end_headers()
                if outer.status != 302:
                    self.wfile.write(json.dumps(outer.reply).encode())

            def log_message(self, *args: Any) -> None:
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


@pytest.fixture
def server() -> Iterator[_Server]:
    srv = _Server()
    yield srv
    srv.httpd.shutdown()
    srv.httpd.server_close()


def test_openai_compat_request_and_answer(server: _Server) -> None:
    server.reply = {"choices": [{"message": {"content": "hallo"}}]}
    provider = OpenAICompatProvider(server.url + "/v1/", "m", 5, api_key=SECRET)
    assert provider.complete(PROMPT) == "hallo"
    path, headers, body = server.seen[0]
    assert path == "/v1/chat/completions"
    assert headers["authorization"] == f"Bearer {SECRET}"
    assert body["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USER"},
    ]
    assert (body["model"], body["max_tokens"], body["temperature"], body["stream"]) == (
        "m", 50, 0.2, False,
    )  # fmt: skip


def test_openai_compat_without_key_sends_no_auth(server: _Server) -> None:
    server.reply = {"choices": [{"message": {"content": "x"}}]}
    OpenAICompatProvider(server.url, "m", 5, api_key=None).complete(PROMPT)
    assert "authorization" not in server.seen[0][1]


def test_anthropic_request_and_answer(server: _Server) -> None:
    server.reply = {"content": [{"type": "text", "text": "hi"}]}
    assert AnthropicProvider(server.url, "m", 5, api_key=SECRET).complete(PROMPT) == "hi"
    path, headers, body = server.seen[0]
    assert path == "/v1/messages"
    assert headers["x-api-key"] == SECRET
    assert headers["anthropic-version"] == "2023-06-01"
    assert body == {
        "model": "m",
        "max_tokens": 50,
        "system": "SYS",
        "messages": [{"role": "user", "content": "USER"}],
    }


@pytest.mark.parametrize("status", [401, 302])
def test_http_errors_and_redirect_refused(server: _Server, status: int) -> None:
    server.status = status
    server.reply = {"error": "nope"}
    with pytest.raises(RuntimeError, match=f"HTTP {status}") as info:
        AnthropicProvider(server.url, "m", 5, api_key=SECRET).complete(PROMPT)
    assert SECRET not in str(info.value)
    assert len(server.seen) == 1


def test_unreachable_host() -> None:
    with pytest.raises(RuntimeError, match="läuft der lokale Server"):
        OpenAICompatProvider("http://127.0.0.1:1", "m", 2, api_key=None).complete(PROMPT)


def test_resolve_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    api = ApiSettings(key_env="WTS_TEST_KEY")
    monkeypatch.delenv("WTS_TEST_KEY", raising=False)
    with pytest.raises(RuntimeError, match="WTS_TEST_KEY nicht gesetzt"):
        resolve_key(api)
    monkeypatch.setenv("WTS_TEST_KEY", SECRET)
    assert resolve_key(api) == SECRET


def test_resolve_key_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    api = ApiSettings(key_env="WTS_TEST_KEY", key_source="keyring")
    monkeypatch.setitem(sys.modules, "keyring", None)  # import raises ImportError
    with pytest.raises(RuntimeError, match="pipx inject whattheshell keyring"):
        resolve_key(api)
    store: dict[tuple[str, str], str] = {}
    fake = types.ModuleType("keyring")
    fake.get_password = lambda service, name: store.get((service, name))  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "keyring", fake)
    with pytest.raises(RuntimeError, match="Schlüsselbund"):
        resolve_key(api)
    store[("whattheshell", "WTS_TEST_KEY")] = SECRET
    assert resolve_key(api) == SECRET


def _script(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", f"{directory}:/usr/bin:/bin")
    return directory


def test_claude_default_call(bin_dir: Path) -> None:
    _script(
        bin_dir, "claude",
        'args="|$*|"\n'
        'for flag in "-p --output-format text" "--strict-mcp-config" "--disable-slash-commands" '
        '"--permission-mode dontAsk"; do\n'
        '  case "$args" in *"$flag"*) ;; *) echo "fehlt: $flag" >&2; exit 3;; esac\n'
        "done\n"
        'prev=""; sys=""; src=missing; tools=missing\n'
        'for a; do [ "$prev" = --system-prompt ] && sys=$a; [ "$prev" = --setting-sources ] && '
        'src="[$a]"; [ "$prev" = --tools ] && tools="[$a]"; prev=$a; done\n'
        '[ "$src" = "[]" ] && [ "$tools" = "[]" ] || { echo "leer fehlt" >&2; exit 4; }\n'
        'echo "system=$sys proxy=$HTTPS_PROXY"; cat; pwd\n',
    )  # fmt: skip
    out = AgentCliProvider("claude", [], 5).complete(PROMPT)
    assert "system=SYS" in out
    assert "USER" in out
    assert not Path(out.splitlines()[-1]).exists()  # temp dir removed


def test_agent_gets_proxy_but_no_other_env(bin_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    monkeypatch.setenv("WTS_OTHER", "x")
    _script(bin_dir, "claude", 'echo "$HTTPS_PROXY|$WTS_OTHER"\n')
    assert AgentCliProvider("claude", [], 5).complete(PROMPT).strip() == "http://proxy:3128|"


def test_codex_disables_mcp(bin_dir: Path) -> None:
    _script(bin_dir, "codex", 'case "$*" in *"-c mcp_servers={}"*) echo ok;; *) exit 3;; esac\n')
    assert AgentCliProvider("codex", [], 5).complete(PROMPT).strip() == "ok"


def test_agent_output_limits_and_control_chars(bin_dir: Path) -> None:
    _script(bin_dir, "claude", "head -c 3000000 /dev/zero\n")
    with pytest.raises(RuntimeError, match="Limit abgeschnitten"):
        AgentCliProvider("claude", [], 5).complete(PROMPT)
    _script(
        bin_dir,
        "codex",
        'tmp=""; while [ $# -gt 0 ]; do [ "$1" = -C ] && tmp=$2; shift; done\n'
        'head -c 3000000 /dev/zero > "$tmp/last.txt"\n',
    )
    with pytest.raises(RuntimeError, match="Limit abgeschnitten"):
        AgentCliProvider("codex", [], 5).complete(PROMPT)
    _script(bin_dir, "claude", "printf '\\033[31mboese' >&2; exit 1\n")
    with pytest.raises(RuntimeError) as info:
        AgentCliProvider("claude", [], 5).complete(PROMPT)
    assert "\x1b" not in str(info.value)


def test_urllib_opener_keeps_proxy_handler() -> None:
    import os
    import subprocess

    code = (
        "from whattheshell.ai.providers.http import _OPENER;"
        "assert any(type(h).__name__ == 'ProxyHandler' for h in getattr(_OPENER, 'handlers'))"
    )
    env = {**os.environ, "HTTPS_PROXY": "http://proxy:3128"}
    subprocess.run([sys.executable, "-c", code], check=True, env=env)  # noqa: S603


def test_codex_default_call_reads_last_txt(bin_dir: Path) -> None:
    _script(
        bin_dir, "codex",
        'tmp=""; while [ $# -gt 0 ]; do [ "$1" = -C ] && tmp=$2; shift; done\n'
        'cat > "$tmp/in.txt"; cp "$tmp/in.txt" "$tmp/last.txt"; echo stdout-ignored\n',
    )  # fmt: skip
    out = AgentCliProvider("codex", [], 5).complete(PROMPT)
    assert out == "SYS\n\nUSER"


def test_custom_command_placeholders(bin_dir: Path) -> None:
    _script(bin_dir, "mytool", 'echo "$1|$2"; cat\n')
    out = AgentCliProvider("claude", ["mytool", "{system}", "{tmp}"], 5).complete(PROMPT)
    first, rest = out.split("\n", 1)
    assert first.startswith("SYS|/") and rest == "USER"


def test_agent_failures(bin_dir: Path) -> None:
    with pytest.raises(RuntimeError, match="`claude` nicht gefunden"):
        AgentCliProvider("claude", [], 5).complete(PROMPT)
    _script(bin_dir, "claude", "echo kaputt >&2; exit 2\n")
    with pytest.raises(RuntimeError, match="Code 2: kaputt"):
        AgentCliProvider("claude", [], 5).complete(PROMPT)
    _script(bin_dir, "claude", "sleep 5\n")
    with pytest.raises(RuntimeError, match="Zeitlimit"):
        AgentCliProvider("claude", [], 0.3).complete(PROMPT)


def test_build_per_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    assert isinstance(build(AiSettings(provider="local")), OpenAICompatProvider)
    assert isinstance(build(AiSettings(provider="agent")), AgentCliProvider)
    api = {"kind": "anthropic", "model": "m"}
    anthropic = build(AiSettings.model_validate({"provider": "api", "api": api}))
    assert isinstance(anthropic, AnthropicProvider)
    api = {"kind": "openai", "model": "m"}
    openai = build(AiSettings.model_validate({"provider": "api", "api": api}))
    assert isinstance(openai, OpenAICompatProvider)
    with pytest.raises(RuntimeError, match="wts ai config set api.model"):
        build(AiSettings(provider="api"))


def test_providers_package_imports_no_provider_module() -> None:
    import subprocess

    code = (
        "import sys, whattheshell.ai.providers as p;"
        "bad=[m for m in sys.modules if m.startswith('whattheshell.ai.providers.')];"
        "assert not bad, bad"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603


@pytest.fixture
def real_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake user HOME with global CLAUDE.md, settings and login files of both agents."""
    home = tmp_path / "realhome"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude/CLAUDE.md").write_text("GLOBAL")
    (home / ".claude/settings.json").write_text("{}")
    (home / ".claude/.credentials.json").write_text("CRED")
    (home / ".codex").mkdir()
    (home / ".codex/config.toml").write_text("x = 1")
    (home / ".codex/auth.json").write_text("AUTH")
    monkeypatch.setenv("HOME", str(home))
    return home


def test_claude_runs_in_throwaway_home(bin_dir: Path, real_home: Path) -> None:
    _script(
        bin_dir, "claude",
        'echo "$HOME|$XDG_CONFIG_HOME|$XDG_CACHE_HOME|$(pwd)"; ls -A "$HOME/.claude"\n'
        'stat -c %a "$HOME/.claude/.credentials.json"; cat "$HOME/.claude/.credentials.json"\n',
    )  # fmt: skip
    head, listing, mode, cred = AgentCliProvider("claude", [], 5).complete(PROMPT).splitlines()
    home, config, cache, cwd = head.split("|")
    assert home != str(real_home) and Path(home).name == "home" and Path(cwd).name == "work"
    assert (config, cache) == (f"{home}/.config", f"{home}/.cache")
    assert Path(cwd).parent == Path(home).parent
    assert (listing, mode, cred) == (".credentials.json", "600", "CRED")  # no CLAUDE.md, settings
    assert not Path(home).parent.exists()


def test_codex_runs_in_throwaway_home_without_user_config(bin_dir: Path, real_home: Path) -> None:
    _script(
        bin_dir, "codex",
        'case "$*" in *"--ignore-user-config --ignore-rules"*) ;; *) exit 3;; esac\n'
        'tmp=""; while [ $# -gt 0 ]; do [ "$1" = -C ] && tmp=$2; shift; done\n'
        'ls -A "$HOME/.codex" > "$tmp/last.txt"; echo "$HOME" >> "$tmp/last.txt"\n',
    )  # fmt: skip
    listing, home = AgentCliProvider("codex", [], 5).complete(PROMPT).splitlines()
    assert listing == "auth.json" and not Path(home).exists()


def test_throwaway_home_removed_after_timeout(
    bin_dir: Path, real_home: Path, tmp_path: Path
) -> None:
    seen = tmp_path / "seen"
    _script(bin_dir, "claude", f'echo "$HOME" > "{seen}"; sleep 5\n')
    with pytest.raises(RuntimeError, match="Zeitlimit"):
        AgentCliProvider("claude", [], 0.5).complete(PROMPT)
    assert not Path(seen.read_text().strip()).parent.exists()


def test_missing_login_file_is_not_an_error(bin_dir: Path, real_home: Path) -> None:
    (real_home / ".claude/.credentials.json").unlink()
    _script(bin_dir, "claude", 'ls -A "$HOME/.claude"; echo end\n')
    assert AgentCliProvider("claude", [], 5).complete(PROMPT).strip() == "end"
