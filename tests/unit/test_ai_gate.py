# SPDX-License-Identifier: AGPL-3.0-or-later
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

import pytest

from whattheshell.ai import AiDisabled, require_enabled
from whattheshell.ai.protocol import make_provider
from whattheshell.cli import main
from whattheshell.settings import Settings


def _forbidden(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("Netzwerk oder Fremdprozess bei ausgeschalteter KI")


def test_require_enabled() -> None:
    settings = Settings()
    with pytest.raises(AiDisabled, match="wts ai enable"):
        require_enabled(settings)
    settings.ai.enabled = True
    require_enabled(settings)


def test_make_provider_gate_comes_before_provider_import(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "whattheshell.ai.providers", raising=False)
    with pytest.raises(AiDisabled):
        make_provider(Settings())
    assert "whattheshell.ai.providers" not in sys.modules


@pytest.mark.parametrize(
    "argv",
    [
        ["ai", "improve-module", "grep"],
        ["ai", "examples", "grep", "--yes"],
        ["ai", "draft-workflow", "zähle Fehler", "--yes"],
        ["ai", "diagnose", "run.json", "a", "--yes"],
    ],
)
def test_disabled_means_no_network_no_process_no_provider(
    argv: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(sys.modules, "whattheshell.ai.providers", raising=False)
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    assert main(argv) == 2
    assert "KI-Funktionen sind ausgeschaltet" in capsys.readouterr().err
    assert "whattheshell.ai.providers" not in sys.modules
    assert not (tmp_path / "cfg").exists()


@pytest.mark.parametrize(
    "argv",
    [["ai", "status"], ["ai", "enable"], ["ai", "config", "set", "provider", "agent"]],
)
def test_settings_commands_work_without_network_process_or_provider(
    argv: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delitem(sys.modules, "whattheshell.ai.providers", raising=False)
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    assert main(argv) == 0
    assert "whattheshell.ai.providers" not in sys.modules
