# SPDX-License-Identifier: AGPL-3.0-or-later
import copy
import logging
from typing import Any

import pytest
from pydantic import ValidationError

from whattheshell.models.workflow import CommandStep, Workflow, iter_steps


def wf(*steps: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"schema_version": 1, "name": "t", "steps": list(steps), **extra}


A = {"id": "a", "tool": "ls"}
B = {"id": "b", "tool": "wc", "stdin": {"pipe": "a"}}


def test_valid_and_kind_default() -> None:
    w = Workflow.model_validate(wf(A, B))
    assert isinstance(w.steps[0], CommandStep)
    assert w.steps[0].kind == "command"


def test_duplicate_id() -> None:
    with pytest.raises(ValidationError, match="mehrfach"):
        Workflow.model_validate(wf(A, {"id": "a", "kind": "message", "text": "x"}))


def test_pipe_to_later_step() -> None:
    with pytest.raises(ValidationError, match="kein vorheriger Schritt"):
        Workflow.model_validate(wf(B, A))


def test_pipe_from_branch_to_earlier_step() -> None:
    cond: dict[str, Any] = {
        "id": "c",
        "kind": "if",
        "condition": {"source": "a.stdout", "is_empty": False},
    }
    cond["then"] = [B]
    Workflow.model_validate(wf(A, cond))


def test_pipe_outside_branch_rejected() -> None:
    cond: dict[str, Any] = {
        "id": "c",
        "kind": "if",
        "condition": {"source": "a.stdout", "is_empty": False},
    }
    cond["then"] = [A]
    with pytest.raises(ValidationError, match="nicht vorher"):
        Workflow.model_validate(wf(cond, {"id": "z", "tool": "wc", "stdin": {"pipe": "a"}}))


def _if(condition: dict[str, Any]) -> dict[str, Any]:
    return wf(A, {"id": "c", "kind": "if", "condition": condition, "then": []})


def test_condition_two_operators() -> None:
    with pytest.raises(ValidationError, match="eq, ne"):
        Workflow.model_validate(_if({"source": "a.stdout", "eq": "x", "ne": "y"}))


def test_condition_no_operator() -> None:
    with pytest.raises(ValidationError, match="keiner"):
        Workflow.model_validate(_if({"source": "a.stdout"}))


def test_stdin_pipe_and_text() -> None:
    bad = {"id": "b", "tool": "wc", "stdin": {"pipe": "a", "text": "x"}}
    with pytest.raises(ValidationError, match="genau eines"):
        Workflow.model_validate(wf(A, bad))


def test_retry_needs_retries() -> None:
    with pytest.raises(ValidationError, match="retries"):
        Workflow.model_validate(wf({**A, "on_error": {"action": "retry"}}))


def test_fallback_duplicate_id() -> None:
    step = {**A, "on_error": {"action": "fallback", "steps": [{"id": "a", "tool": "true"}]}}
    with pytest.raises(ValidationError, match="mehrfach"):
        Workflow.model_validate(wf(step))


def test_invalid_template() -> None:
    with pytest.raises(ValidationError, match="Template"):
        Workflow.model_validate(wf({"id": "m", "kind": "message", "text": "{{ 1bad }}"}))


def test_layout_unknown_id_dropped(caplog: pytest.LogCaptureFixture) -> None:
    layout = {"nodes": {"a": {"x": 0, "y": 0}, "zz": {"x": 1, "y": 1}}}
    with caplog.at_level(logging.WARNING):
        w = Workflow.model_validate(wf(A, layout=layout))
    assert w.layout is not None
    assert list(w.layout.nodes) == ["a"]
    assert "zz" in caplog.text


def test_iter_steps_document_order() -> None:
    doc = wf(
        {
            "id": "c",
            "kind": "if",
            "condition": {"source": "var.x", "is_empty": True},
            "then": [{"id": "t", "tool": "ls"}],
            "else": [{"id": "e", "kind": "message", "text": "x"}],
        },
        {"id": "f", "kind": "foreach", "source": "var.x", "body": [{"id": "g", "tool": "ls"}]},
        {"id": "z", "tool": "ls"},
        variables={"x": {}},
    )
    w = Workflow.model_validate(copy.deepcopy(doc))
    assert [s.id for s in iter_steps(w.steps)] == ["c", "t", "e", "f", "g", "z"]


def msg(step: dict[str, Any], *before: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return wf(*before, step, **extra)


def message(text: str, step_id: str = "m") -> dict[str, Any]:
    return {"id": step_id, "kind": "message", "text": text}


def _cond(source: str) -> dict[str, Any]:
    return {"id": "c", "kind": "if", "condition": {"source": source, "is_empty": True}, "then": []}


@pytest.mark.parametrize(
    ("doc", "text"),
    [
        (msg(_cond("zz.stdout"), A), "unbekannt"),
        (msg(message("{{ var.nope }}")), "deklarierte Variable"),
        (wf(message("{{ a.stdout }}"), A), "nicht vorher"),
        (msg(message("{{ item }}")), "foreach"),
        (msg(message("{{ a.bogus }}"), A), "stdout"),
        (msg(message("{{ a.b.c }}"), A), "ungültiges Template"),
        (msg({"id": "p", "tool": "wc", "stdin": {"pipe": "nix"}}, A), "stdin.pipe"),
        (
            msg({"id": "p", "kind": "foreach", "source": "file:x", "as": "a", "body": []}, A),
            "überdeckt",
        ),
        (wf(message("x", "var")), "reserviert"),
        (wf(message("x", "item")), "reserviert"),
        (wf(A, variables={"Bad": {}}), "pattern"),
        (wf(message("x"), {"id": "n", "kind": "message"}), "Field required"),
        (wf({"id": "n", "label": "x"}), "braucht `kind` oder `tool`"),
        (msg({**A, "id": "e", "env": {"K": "{{ var.x"}}), "ungültiges Template"),
        (msg({**A, "id": "e", "cwd": "{{ var.x }}"}), "deklarierte Variable"),
        (msg(_cond("x.stdout")), "unbekannt"),
        (
            msg(
                {
                    "id": "c",
                    "kind": "if",
                    "condition": {"source": "a.stdout", "regex": "("},
                    "then": [],
                },
                A,
            ),
            "regex",
        ),
        (msg({**A, "id": "e", "tool": "../x"}), "pattern"),
        (msg({**A, "id": "e", "tool": "-x"}), "pattern"),
        (msg({**A, "id": "e", "ok_exit_codes": [256]}), "less than or equal"),
        (wf(A, variables={"s": {"type": "secret", "default": "x"}}), "secret"),
        (
            msg(
                {
                    "id": "c",
                    "kind": "if",
                    "condition": {"source": "a.stdout", "is_empty": True},
                    "then": [message("x", "t")],
                    "else": [message("{{ t.stdout }}", "e")],
                },
                A,
            ),
            "nicht vorher",
        ),
    ],
)
def test_invalid(doc: dict[str, Any], text: str) -> None:
    with pytest.raises(ValidationError, match=text):
        Workflow.model_validate(doc)


def test_valid_references() -> None:
    each = {
        "id": "f",
        "kind": "foreach",
        "source": "a.stdout",
        "as": "datei",
        "body": [message("{{ datei }} {{ item }} {{ a.lines }} {{ var.x }}", "m1")],
    }
    fb = {
        **A,
        "id": "g",
        "on_error": {"action": "fallback", "steps": [message("{{ a.stdout }}", "m2")]},
    }
    w = Workflow.model_validate(wf(A, each, fb, variables={"x": {}}))
    assert len(list(iter_steps(w.steps))) == 5


def test_round_trip_uses_aliases() -> None:
    doc = wf(
        A,
        {
            "id": "c",
            "kind": "if",
            "condition": {"source": "a.stdout", "is_empty": True},
            "then": [message("x", "t")],
            "else": [message("y", "e")],
        },
        {
            "id": "f",
            "kind": "foreach",
            "source": "a.stdout",
            "as": "d",
            "body": [message("{{ d }}", "g")],
        },
    )
    first = Workflow.model_validate(doc)
    dumped = first.model_dump()
    assert Workflow.model_validate(dumped) == first
    assert "else" in dumped["steps"][1]
    assert "else_" not in dumped["steps"][1]
    assert dumped["steps"][2]["as"] == "d"
    assert "as_" not in dumped["steps"][2]


def test_format_validation_error_has_path() -> None:
    from whattheshell.models.validation import format_validation_error

    with pytest.raises(ValidationError) as info:
        Workflow.model_validate(wf({"id": "m", "kind": "wait", "seconds": -1}))
    out = format_validation_error(info.value, "x.yaml")
    assert out.startswith("x.yaml: steps[0].wait.seconds")


def test_escaped_braces() -> None:
    Workflow.model_validate(wf({**A, "args": {"format": "\\{{.Names}}"}}))
    with pytest.raises(ValidationError, match="ungültiges Template"):
        Workflow.model_validate(wf({**A, "args": {"format": "{{.Names}}"}}))


def test_set_variable_must_be_declared() -> None:
    step = {"id": "merke", "kind": "set", "variable": "anzahl", "value": "{{ a.stdout }}"}
    Workflow.model_validate(wf(A, step, variables={"anzahl": {}}))
    with pytest.raises(ValidationError, match="undeklarierte Variable 'anzahl'"):
        Workflow.model_validate(wf(A, step))


def test_foreach_as_reserved() -> None:
    step = {"id": "f", "kind": "foreach", "source": "a.stdout", "as": "var", "body": []}
    with pytest.raises(ValidationError, match="reserviert"):
        Workflow.model_validate(wf(A, step))
