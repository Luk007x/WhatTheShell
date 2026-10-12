# SPDX-License-Identifier: AGPL-3.0-or-later
import json
from pathlib import Path

import pytest

from whattheshell.modules.loader import DocumentError, load_module_file, load_workflow_file

VALID = "schema_version: 1\ntool: grep\nsummary: S\n"


def write(tmp_path: Path, text: str, name: str = "grep.module.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_valid(tmp_path: Path) -> None:
    module = load_module_file(write(tmp_path, VALID))
    assert module.tool == "grep"
    assert module.summary == "S"


def test_json(tmp_path: Path) -> None:
    text = json.dumps({"schema_version": 1, "tool": "ls"})
    assert load_module_file(write(tmp_path, text, "ls.module.json")).tool == "ls"


def test_yaml_syntax_error_has_line(tmp_path: Path) -> None:
    with pytest.raises(DocumentError) as info:
        load_module_file(write(tmp_path, "schema_version: 1\ntool: [grep\nx: y\n"))
    assert info.value.line is not None
    assert str(info.value).startswith(f"{tmp_path / 'grep.module.yaml'}:{info.value.line}: ")


def test_validation_error_has_path_and_line(tmp_path: Path) -> None:
    text = "schema_version: 1\ntool: grep\noptions:\n  - id: a\n  - id: B\n    flags: [-x]\n"
    with pytest.raises(DocumentError) as info:
        load_module_file(write(tmp_path, text))
    assert "options[1].id" in info.value.message
    assert info.value.line == 5


def test_validation_error_missing_field_falls_back_to_parent(tmp_path: Path) -> None:
    with pytest.raises(DocumentError) as info:
        load_module_file(write(tmp_path, "schema_version: 1\n"))
    assert "tool" in info.value.message


def test_wrong_suffix(tmp_path: Path) -> None:
    with pytest.raises(DocumentError, match=r"muss auf \.module\.yaml enden"):
        load_module_file(write(tmp_path, VALID, "grep.yaml"))


def test_top_level_list(tmp_path: Path) -> None:
    with pytest.raises(DocumentError, match="Objekt"):
        load_module_file(write(tmp_path, "- a\n- b\n"))


def test_str_without_line(tmp_path: Path) -> None:
    err = DocumentError(tmp_path / "x", None, "m")
    assert str(err) == f"{tmp_path / 'x'}: m"


def test_workflow_file(tmp_path: Path) -> None:
    text = "schema_version: 1\nname: W\nsteps: []\n"
    path = write(tmp_path, text, "w.workflow.yaml")
    assert load_workflow_file(path).name == "W"
    with pytest.raises(DocumentError, match=r"\.workflow\.yaml"):
        load_workflow_file(write(tmp_path, text, "w.yaml"))


def test_alias_bomb(tmp_path: Path) -> None:
    import time

    lines = ["a: &a [x,x,x,x,x,x,x,x,x]"]
    prev = "a"
    for name in "bcdefghi":
        lines.append(f"{name}: &{name} [{','.join('*' + prev for _ in range(9))}]")
        prev = name
    start = time.monotonic()
    with pytest.raises(DocumentError, match="Aliase"):
        load_module_file(write(tmp_path, "schema_version: 1\ntool: x\n" + "\n".join(lines) + "\n"))
    assert time.monotonic() - start < 1


def test_deep_nesting_and_scan(tmp_path: Path) -> None:
    from whattheshell.modules.registry import ModuleRegistry

    write(tmp_path, "schema_version: 1\ntool: " + "[" * 100000 + "\n", "deep.module.yaml")
    write(tmp_path, VALID)
    with pytest.raises(DocumentError):
        load_module_file(tmp_path / "deep.module.yaml")
    registry = ModuleRegistry([tmp_path])
    registry.scan()
    assert len(registry.for_tool("grep")) == 1
    assert len(registry.errors) == 1


def test_too_big(tmp_path: Path) -> None:
    path = write(tmp_path, VALID + "#" * 1_048_577)
    with pytest.raises(DocumentError, match="zu groß"):
        load_module_file(path)
