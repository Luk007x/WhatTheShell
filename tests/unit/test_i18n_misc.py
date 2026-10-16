# SPDX-License-Identifier: AGPL-3.0-or-later
"""English texts of the ai, modules, sandbox and safety packages."""

import shutil
from pathlib import Path

import pytest

from whattheshell import i18n
from whattheshell.ai.check import check
from whattheshell.ai.protocol import Prompt
from whattheshell.ai.providers import agent_cli
from whattheshell.i18n import use_lang
from whattheshell.modules.loader import DocumentError, load_module_file
from whattheshell.sandbox import self_test
from whattheshell.settings import Settings


@pytest.fixture(autouse=True)
def _debug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WTS_I18N_DEBUG", "1")
    i18n.missing.clear()


def test_sandbox_hint_without_bwrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    with use_lang("en"):
        status = self_test()
    assert status.reason == "bubblewrap (bwrap) is not installed."
    assert not i18n.missing


def test_document_error_english(tmp_path: Path) -> None:
    bad = tmp_path / "x.module.yaml"
    bad.write_text("a: [1\n")
    with use_lang("en"), pytest.raises(DocumentError) as info:
        load_module_file(bad)
    assert "Invalid YAML" in info.value.message
    assert not i18n.missing


def test_check_ai_off() -> None:
    settings = Settings()
    settings.ai.enabled = False
    with use_lang("en"):
        item = check(settings).items[0]
    assert (item.name, item.detail) == ("AI off", "AI features are switched off.")
    assert not i18n.missing


def test_agent_missing_program(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_cli, "run_limited", lambda *a, **k: None)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    provider = agent_cli.AgentCliProvider("claude", 5.0)
    with use_lang("en"), pytest.raises(RuntimeError) as info:
        provider.complete(Prompt(system="s", user="u"))
    assert str(info.value) == "Program `claude` not found"
    assert not i18n.missing
