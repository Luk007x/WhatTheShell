# SPDX-License-Identifier: AGPL-3.0-or-later
import re
from pathlib import Path

import pytest

from whattheshell import i18n
from whattheshell.cli import main

HELP_COMMANDS = (
    [],
    ["run"],
    ["gui"],
    ["workflows"],
    ["workflows", "import"],
    ["ai"],
    ["ai", "config", "set"],
    ["ai", "improve-module"],
    ["ai", "diagnose"],
    ["scaffold"],
    ["inspect"],
    ["example"],
    ["terminal", "transcripts"],
)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)


def _english(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WTS_LANG", "en")
    i18n.set_lang("en")  # the conftest fixture resets its own token afterwards


def _help(args: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as exit_info:
        main([*args, "--help"])
    assert exit_info.value.code == 0
    return capsys.readouterr().out


def test_help_is_english(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _english(monkeypatch)
    out = _help([], capsys)
    assert not re.search("[äöüÄÖÜß]", out)
    assert "usage" in out.lower()
    assert "options" in out
    assert "Run a workflow" in out


def test_error_message_follows_language(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _english(monkeypatch)
    assert main(["workflows", "accept", "nope"]) == 1
    assert "Workflow 'nope' does not exist" in capsys.readouterr().err
    assert main(["--lang", "de", "workflows", "accept", "nope"]) == 1
    assert "Workflow 'nope' gibt es nicht" in capsys.readouterr().err


def test_help_german_with_lang_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _english(monkeypatch)
    assert "Workflow ausführen" in _help(["--lang", "de"], capsys)


def test_catalog_complete_for_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _english(monkeypatch)
    monkeypatch.setenv("WTS_I18N_DEBUG", "1")
    i18n.missing.clear()
    for command in HELP_COMMANDS:
        out = _help(command, capsys)
        assert not re.search("[äöüÄÖÜß]", out), command
    assert i18n.missing == set()
