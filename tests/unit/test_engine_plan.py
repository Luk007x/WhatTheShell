# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest

from whattheshell.engine import plan, plan_text
from whattheshell.models.workflow import Workflow

from .test_engine_runner import echo, make_runner, make_workflow, tools  # noqa: F401

pytestmark = pytest.mark.usefixtures("tools")


def test_plan_text_shows_everything_without_running(
    tmp_path: Path,
) -> None:
    wf = make_workflow(
        [
            echo("a", "{{ var.v }}"),
            {"id": "r", "tool": "git", "extra_args": ["{{ a.stdout }}"]},
            {
                "id": "chk",
                "kind": "if",
                "condition": {"source": "a.stdout", "contains": "z"},
                "then": [{"id": "m", "kind": "message", "text": "yes"}],
                "else": [{"id": "n", "kind": "message", "text": "no"}],
            },
        ],
        {"v": {"default": "hello world"}},
    )
    runner, events = make_runner(tmp_path)
    text = plan_text(plan(runner.prepare(wf, {})))
    assert "echo-args 'hello world'" in text
    assert "caution" in text and "{{ a.stdout }}" in text
    assert "then:" in text and "else:" in text and "a.stdout contains 'z'" in text
    assert events == [] and not (tmp_path / "counter").exists()


def _text(tmp_path: Path, wf: Workflow, overrides: dict[str, str] | None = None) -> str:
    runner, _ = make_runner(tmp_path)
    return plan_text(plan(runner.prepare(wf, overrides or {})))


def test_plan_foreach_and_fallback_blocks(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            {
                "id": "x",
                "tool": "fail",
                "on_error": {"action": "fallback", "steps": [echo("fb", "f")]},
            },
            {
                "id": "loop",
                "kind": "foreach",
                "source": "x.stdout",
                "as": "d",
                "body": [echo("e", "{{ d }}")],
            },
        ]
    )
    text = _text(tmp_path, wf)
    assert "fallback:" in text and "body:" in text and "x.stdout als d" in text
    assert "{{ d }}" in text


def test_plan_masks_secrets(tmp_path: Path) -> None:
    wf = make_workflow([echo("a", "{{ var.pw }}")], {"pw": {"type": "secret"}})
    text = _text(tmp_path, wf, {"pw": "hunter2"})
    assert "hunter2" not in text and "***" in text


def test_plan_flags_cwd_and_stdin_file_outside_root(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            echo("a", "x", cwd="/etc"),
            {"id": "b", "tool": "mycat", "stdin": {"file": "{{ var.f }}"}},
            echo("c", "x", cwd="sub"),
        ],
        {"f": {"default": "/etc/hostname"}},
    )
    text = _text(tmp_path, wf)
    assert "Arbeitsverzeichnis außerhalb des Workflow-Ordners" in text
    assert "liest Datei außerhalb" in text
    assert text.count("<caution") == 2


def test_plan_terminal_step_is_marked_interactive(tmp_path: Path) -> None:
    wf = make_workflow([{"id": "t", "kind": "terminal", "tool": "echo-args", "network": True}])
    text = _text(tmp_path, wf)
    assert "t [terminal] interaktiv, wird im Trockenlauf übersprungen: echo-args" in text
    assert "caution: interaktiv; Netzzugang" in text


def test_plan_text_ask(tmp_path: Path) -> None:
    wf = make_workflow(
        [{"id": "q", "kind": "ask", "title": "Wer?", "fields": ["v"], "buttons": ["Ja", "Nein"]}],
        {"v": {}},
    )
    runner, _ = make_runner(tmp_path, ask=lambda request: None)
    assert "Abfrage „Wer?“: v, Knöpfe: Ja, Nein" in plan_text(plan(runner.prepare(wf, {})))
