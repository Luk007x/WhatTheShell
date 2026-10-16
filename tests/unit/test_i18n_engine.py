# SPDX-License-Identifier: AGPL-3.0-or-later
"""Engine, model and settings messages: English without umlauts, German unchanged, no gaps."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from whattheshell import i18n
from whattheshell.catalog import Catalog
from whattheshell.engine import ArgvError, TemplateError, build_argv
from whattheshell.engine.runner import RunError, Runner
from whattheshell.engine.template import Context, render
from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import InputSpec
from whattheshell.models.workflow import Workflow
from whattheshell.settings import AgentSettings


def _unknown_variable(tmp_path: Path) -> str:
    wf = Workflow.model_validate({"schema_version": 1, "name": "t", "steps": []})
    runner = Runner(Catalog(cache_dir=tmp_path / "cache"), confirm=lambda r: True, cwd=tmp_path)
    with pytest.raises(RunError) as err:
        runner.prepare(wf, {"other": "1"})
    return str(err.value)


def _template(tmp_path: Path) -> str:
    with pytest.raises(TemplateError) as err:
        render("{{ var.x }}", Context({}, {}))
    return str(err.value)


def _argv(tmp_path: Path) -> str:
    spec = CommandSpec(name=["tool"], inputs=[InputSpec(id="path", required=True)])
    with pytest.raises(ArgvError) as err:
        build_argv(spec, {})
    return str(err.value)


def _duplicate_step(tmp_path: Path) -> str:
    step = {"id": "a", "kind": "message", "text": "x"}
    with pytest.raises(ValidationError) as err:
        Workflow.model_validate({"schema_version": 1, "name": "t", "steps": [step, step]})
    return str(err.value)


def _settings(tmp_path: Path) -> str:
    with pytest.raises(ValidationError) as err:
        AgentSettings.model_validate({"command": ["claude"]})
    return str(err.value)


CASES: list[tuple[Callable[[Path], str], str]] = [
    (_unknown_variable, "Unbekannte Variable"),
    (_template, "Unbekannte Variable 'x'"),
    (_argv, "Pflichteingabe fehlt"),
    (_duplicate_step, "kommt mehrfach vor"),
    (_settings, "wird nicht mehr unterstützt"),
]


@pytest.mark.parametrize(("case", "german"), CASES)
def test_english_and_german(case: Callable[[Path], str], german: str, tmp_path: Path) -> None:
    with i18n.use_lang("de"):
        assert german in case(tmp_path)
    with i18n.use_lang("en"):
        text = case(tmp_path)
    assert german not in text and not re.search("[äöüÄÖÜß]", text)


def test_no_missing_catalog_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WTS_I18N_DEBUG", "1")
    i18n.missing.clear()
    with i18n.use_lang("en"):
        for case, _german in CASES:
            case(tmp_path)
    assert i18n.missing == set()
