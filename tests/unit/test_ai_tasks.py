# SPDX-License-Identifier: AGPL-3.0-or-later
import os
from pathlib import Path

import pytest

from whattheshell.ai import tasks
from whattheshell.ai.approve import Approval, apply, propose
from whattheshell.ai.diff import unified
from whattheshell.ai.fake import FakeProvider
from whattheshell.ai.protocol import Prompt
from whattheshell.modules.store import validate_module_text, validate_workflow_text

MODULE = "schema_version: 1\ntool: grep\ndisplay_name: grep\n"
WORKFLOW = "schema_version: 1\nname: Mein Test\nsteps:\n  - { id: a, kind: message, text: hi }\n"


def test_improve_module_prompt_has_template_and_inputs() -> None:
    prompt = tasks.improve_module(
        "grep", current_raw=MODULE, inspect_json='{"INSPECT": 1}', authoring_doc="DOKU-TEXT"
    )
    assert "Du schreibst ein WhatTheShell-Modul für den Befehl grep" in prompt.system
    assert "ohne Markdown-Zäune" in prompt.system and "i18n.en" in prompt.system
    for expected in ('{"INSPECT": 1}', "DOKU-TEXT", MODULE):
        assert expected in prompt.user
    new = tasks.improve_module("grep", current_raw=None, inspect_json="{}", authoring_doc="")
    assert "Aktuelles Modul" not in new.user and "neues Modul" in new.user


def test_examples_and_workflow_prompts() -> None:
    assert "Beispiele" in tasks.generate_examples("grep", MODULE, "{}").user
    prompt = tasks.draft_workflow("zähle Fehler", "grep: patterns", "FORMAT-AUSZUG")
    assert "zähle Fehler" in prompt.user and "FORMAT-AUSZUG" in prompt.user
    assert "{{ var.name }}" in prompt.system and "id" in prompt.system


def test_diagnose_without_output_sends_no_stdout() -> None:
    step = {
        "command": "grep x",
        "exit_code": 2,
        "stdout": "GEHEIM-OUT",
        "stderr": "boom\nzweite",
        "started": "2026-01-01T10:00:00",
        "finished": "2026-01-01T10:00:02.5",
        "ok": False,
    }
    user = tasks.diagnose(step, include_output=False).user
    assert "grep x" in user and "Exit-Code: 2" in user and "Dauer: 2.50s" in user
    assert "fehlgeschlagen" in user
    assert "GEHEIM-OUT" not in user and "boom" not in user and "zweite" not in user
    full = tasks.diagnose({**step, "stdout": "x" * 9000}, include_output=True).user
    assert "zweite" in full and "boom" in full and len(full) < 5000 + 500 and "[gekürzt]" in full


def test_extract_yaml() -> None:
    assert tasks.extract_yaml(f"Hier:\n```yaml\n{MODULE}```\nViel Spaß") == MODULE
    assert tasks.extract_yaml(f"Gern!\n\n{MODULE}") == MODULE
    assert tasks.extract_yaml(f"```\n{MODULE}") == MODULE
    assert tasks.extract_yaml(MODULE) == MODULE


def test_sanitize_and_known_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    assert tasks.sanitize("a sk-123 b\x1b[0m", ["sk-123"]) == "a *** b[0m"
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CODEX_API_KEY", "MEIN_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_API_KEY", "abc")
    monkeypatch.setenv("MEIN_KEY", "langerer-wert")
    assert tasks.known_keys("MEIN_KEY") == ["langerer-wert", "abc"]


def test_validate_texts() -> None:
    module, errors = validate_module_text(MODULE)
    assert module is not None and module.tool == "grep" and errors == []
    module, errors = validate_module_text(MODULE + "erfunden: 1\n")
    assert module is None and "erfunden" in errors[0] and "ai.module.yaml" not in errors[0]
    workflow, errors = validate_workflow_text(WORKFLOW)
    assert workflow is not None and errors == []
    assert validate_workflow_text("name: x\n")[0] is None


def test_fake_provider_records() -> None:
    fake = FakeProvider(["eins"])
    prompt = Prompt("s", "u")
    assert fake.complete(prompt) == "eins" and fake.prompts == [prompt]
    with pytest.raises(RuntimeError):
        fake.complete(prompt)


def test_unified() -> None:
    assert unified("a\n", "a\n", "x") == ""
    text = unified("a\nb\n", "a\nc\n", "x")
    assert "-b" in text and "+c" in text and "x (Vorschlag)" in text
    assert "/dev/null" in unified(None, "a\n", "x")


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    return tmp_path / "cfg" / "whattheshell"


def test_apply_writes_only_allowed(config: Path, tmp_path: Path) -> None:
    written = apply(Approval("module", Path("grep.module.yaml"), None, MODULE, "", []))
    assert written.stat().st_mode & 0o777 == 0o600
    assert written == config / "modules" / "grep.module.yaml" and written.read_text() == MODULE
    wf = apply(Approval("workflow", Path("t.workflow.yaml"), None, WORKFLOW, "", []))
    assert wf == config / "workflows" / "t.workflow.yaml"
    for target in (
        tmp_path / "evil.module.yaml",
        Path("../evil.module.yaml"),
        Path("sub/x.module.yaml"),
        Path("grep.txt"),
    ):
        with pytest.raises(ValueError):
            apply(Approval("module", target, None, MODULE, "", []))
    assert not (tmp_path / "evil.module.yaml").exists()


def test_apply_refuses_errors_text_and_symlink(config: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        apply(Approval("module", Path("a.module.yaml"), None, MODULE, "", ["Fehler"]))
    with pytest.raises(ValueError):
        apply(Approval("text", None, None, "x", "", []))
    (config / "modules").mkdir(parents=True)
    victim = tmp_path / "victim"
    victim.write_text("orig")
    os.symlink(victim, config / "modules" / "l.module.yaml")
    link = config / "modules" / "l.module.yaml"
    apply(Approval("module", Path("l.module.yaml"), None, MODULE, "", []))
    assert victim.read_text() == "orig"  # replaced, never written through
    assert not link.is_symlink() and link.read_text() == MODULE
    assert not (config / "modules" / "a.module.yaml").exists()


def test_lowered_safety_warning() -> None:
    caution = MODULE + "safety: caution\n"
    safe = MODULE + "safety: safe\n"
    approval = propose("module", Path("grep.module.yaml"), caution, safe, [])
    assert approval.diff.startswith("ACHTUNG: Sicherheitsklasse wird von caution auf safe gesenkt")
    assert not propose("module", None, safe, caution, []).diff.startswith("ACHTUNG")
    assert not propose("module", None, None, safe, []).diff.startswith("ACHTUNG")
    options = "options:\n  - {id: a, flags: ['-a'], type: bool, safety: dangerous}\n"
    lowered = options.replace("dangerous", "safe")
    assert "Option a" in propose("module", None, MODULE + options, MODULE + lowered, []).diff
