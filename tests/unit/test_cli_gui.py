# SPDX-License-Identifier: AGPL-3.0-or-later
"""`wts gui` instance detection, status and desktop entry."""

import os
import sys
import webbrowser
from pathlib import Path

import pytest

from whattheshell import cli, instance
from whattheshell.instance import InstanceInfo


@pytest.fixture(autouse=True)
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(instance, "_proc_cmdline", lambda pid: "wts gui")


def _fake_running() -> InstanceInfo:
    info = InstanceInfo(
        os.getpid(), 4321, "http://127.0.0.1:4321/#token=t", 1.0, instance.own_start_ticks()
    )
    instance.write(info)
    return info


def test_status_not_running(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["gui", "status"]) == 3
    assert "Nicht gestartet" in capsys.readouterr().out


def test_status_running(capsys: pytest.CaptureFixture[str]) -> None:
    _fake_running()
    assert cli.main(["gui", "status"]) == 0
    assert "Port 4321" in capsys.readouterr().out


def test_second_gui_starts_no_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _fake_running()
    lock = instance.acquire_lock()  # the "running server" holds the lock
    assert lock is not None
    opened: list[str] = []
    monkeypatch.setattr(cli, "_serve", lambda *a: pytest.fail("second server started"))

    def fake_open(url: str) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", fake_open)
    assert cli.main(["gui"]) == 0
    assert "Läuft bereits auf Port 4321" in capsys.readouterr().out
    assert len(opened) == 1
    assert cli.main(["gui", "--no-browser"]) == 0
    assert len(opened) == 1
    os.close(lock)


def test_stop_without_instance(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["gui", "stop"]) == 0
    assert "Nicht gestartet" in capsys.readouterr().out


def test_install_desktop(tmp_path: Path) -> None:
    assert cli.main(["gui", "--install-desktop"]) == 0
    text = (tmp_path / "data" / "applications" / "whattheshell.desktop").read_text(encoding="utf-8")
    assert "Exec=" in text and text.splitlines()[0] == "[Desktop Entry]"
    assert "gui start" in text and "Terminal=false" in text


def test_install_desktop_quotes_exec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "/opt/my 50%/py")
    assert cli.main(["gui", "--install-desktop"]) == 0
    text = (tmp_path / "data" / "applications" / "whattheshell.desktop").read_text(encoding="utf-8")
    assert 'Exec="/opt/my 50%%/py" -m whattheshell gui start' in text
