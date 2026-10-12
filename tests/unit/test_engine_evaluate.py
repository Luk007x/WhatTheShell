# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
from typing import Any

import pytest

from whattheshell.engine import Context, EvalError, StepOutput, evaluate
from whattheshell.models.workflow import Condition


def run(source: str, stdout: str = "", tmp: Path | None = None, **op: Any) -> bool:
    ctx = Context({"v": "42"}, {"s": StepOutput(stdout, "", 0)}, {"item": "it"})
    return evaluate(Condition(source=source, **op), ctx, cwd=tmp or Path.cwd())


@pytest.mark.parametrize(
    ("stdout", "op", "expected"),
    [
        ("ok\n", {"eq": "ok"}, True),
        ("ok\n", {"ne": "ok"}, False),
        ("7\n", {"eq": 7}, True),
        ("7.0", {"eq": 7}, True),
        ("abc", {"eq": 7}, False),
        ("hello", {"contains": "ell"}, True),
        ("abc123", {"regex": r"\d+$"}, True),
        ("abc", {"regex": r"^\d"}, False),
        (" \n", {"is_empty": True}, True),
        ("x", {"is_empty": True}, False),
        ("x", {"is_empty": False}, True),
        ("a\nb\nc\n\n", {"line_count_gt": 2}, True),
        ("a\nb\n", {"line_count_eq": 2}, True),
        ("", {"line_count_eq": 0}, True),
        ("found 12 items 5", {"number_gt": 11}, True),
        ("x -3.5", {"number_lt": 0}, True),
        ("n=4", {"number_eq": 4}, True),
        ('{"a": {"b": [{"c": 1}]}}', {"json_path": "a.b[0].c"}, True),
        ('{"a": {"b": [{"c": 1}]}}', {"json_path": ".a.b[1]"}, False),
        ('{"a": null}', {"json_path": ".a"}, False),
        ('{"a": 1}', {"json_path": ".x"}, False),
    ],
)
def test_operators(stdout: str, op: dict[str, Any], expected: bool) -> None:
    assert run("s.stdout", stdout, **op) is expected


def test_other_sources() -> None:
    assert run("var.v", number_eq=42)
    assert run("item", eq="it")
    assert run("s.exit_code", eq=0)


def test_errors() -> None:
    with pytest.raises(EvalError, match="Keine Zahl"):
        run("s.stdout", "abc", number_gt=1)
    with pytest.raises(EvalError, match="JSON"):
        run("s.stdout", "nope", json_path=".a")
    with pytest.raises(EvalError, match="Unbekannt"):
        run("var.zz", eq="x")


def test_file_source(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("one\ntwo\n")
    assert run("file:f.txt", tmp=tmp_path, line_count_eq=2)
    assert run("file:f.txt", tmp=tmp_path, file_exists=True)
    assert run("file:nope", tmp=tmp_path, file_exists=False)
    with pytest.raises(EvalError, match="existiert nicht"):
        run("file:nope", tmp=tmp_path, eq="")


def test_file_escape(tmp_path: Path) -> None:
    for op in ({"eq": "x"}, {"file_exists": True}):
        with pytest.raises(EvalError, match="außerhalb"):
            run("file:../x", tmp=tmp_path, **op)
    with pytest.raises(EvalError, match="außerhalb"):
        run("file:/etc/passwd", tmp=tmp_path, eq="x")


def test_paths_inside(tmp_path: Path) -> None:
    from whattheshell.paths import inside

    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "link").symlink_to("/etc")
    assert inside(tmp_path / "d" / "x", tmp_path)
    assert not inside(tmp_path / "d" / ".." / "..", tmp_path)
    assert not inside(tmp_path / "d" / "link", tmp_path)
