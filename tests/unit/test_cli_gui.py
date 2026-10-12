# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import socket
import webbrowser
from pathlib import Path
from typing import Any

import pytest

from whattheshell import cli
from whattheshell.cli import main


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.chdir(tmp_path)


def test_refuses_root(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    served: list[int] = []
    monkeypatch.setattr(cli, "_serve", lambda app, sock: served.append(1))
    assert main(["gui", "--no-browser"]) == 1
    assert "root" in capsys.readouterr().err
    assert served == []


def test_prints_url_and_opens_redirect_file_without_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    opened: list[str] = []
    seen: dict[str, Any] = {}

    def fake_serve(app: Any, sock: socket.socket) -> None:
        seen["port"] = sock.getsockname()[1]
        page = Path(opened[0].removeprefix("file://"))
        seen["mode"] = page.stat().st_mode & 0o777
        seen["dir_mode"] = page.parent.stat().st_mode & 0o777
        seen["text"] = page.read_text(encoding="utf-8")
        seen["page"] = page

    monkeypatch.setattr(cli, "_serve", fake_serve)

    def fake_open(url: str) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)
    assert main(["gui"]) == 0
    out = capsys.readouterr().out
    port = seen["port"]
    assert port > 0
    token = out.split("#token=")[1].strip()
    assert out.startswith(f"http://127.0.0.1:{port}/#token=")
    assert len(token) >= 43
    assert opened[0].startswith("file://")
    assert "token" not in opened[0]
    assert seen["mode"] == 0o600
    assert seen["dir_mode"] == 0o700
    assert f"http://127.0.0.1:{port}/#token={token}" in seen["text"]
    assert not seen["page"].exists()  # removed on exit


def test_no_browser_writes_no_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "_serve", lambda app, sock: None)
    monkeypatch.setattr(webbrowser, "open", lambda url: pytest.fail("browser opened"))
    assert main(["gui", "--no-browser"]) == 0
    assert not (tmp_path / "xdg-cache" / "whattheshell" / "gui").exists()


def test_explicit_port_is_bound_before_serving(monkeypatch: pytest.MonkeyPatch) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]
    ports: list[int] = []
    monkeypatch.setattr(cli, "_serve", lambda app, sock: ports.append(sock.getsockname()[1]))
    assert main(["gui", "--no-browser", "--port", str(free)]) == 0
    assert ports == [free]


def test_port_in_use(capsys: pytest.CaptureFixture[str]) -> None:
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        assert main(["gui", "--no-browser", "--port", str(busy.getsockname()[1])]) == 1
    assert "--port" in capsys.readouterr().err
