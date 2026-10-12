# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest

from whattheshell.modules.registry import ModuleRegistry


def write(directory: Path, name: str, summary: str = "S", tool: str = "grep") -> Path:
    directory.mkdir(exist_ok=True)
    path = directory / name
    path.write_text(f"schema_version: 1\ntool: {tool}\nsummary: {summary}\n", encoding="utf-8")
    return path


def test_priority_order(tmp_path: Path) -> None:
    low, high = tmp_path / "low", tmp_path / "high"
    write(high, "grep.module.yaml", "high")
    write(low, "grep.module.yaml", "low")
    registry = ModuleRegistry([low, high])
    registry.scan()
    assert [m.module.summary for m in registry.for_tool("grep")] == ["low", "high"]
    assert [m.priority for m in registry.for_tool("grep")] == [0, 1]
    assert len(registry.all()) == 2


def test_broken_file_only_in_errors(tmp_path: Path) -> None:
    write(tmp_path, "ls.module.yaml", tool="ls")
    bad = tmp_path / "bad.module.yaml"
    bad.write_text("- x\n")
    registry = ModuleRegistry([tmp_path])
    registry.scan()
    assert list(registry.modules) == ["ls"]
    assert [e.path for e in registry.errors] == [bad]


def test_reload_changed_and_deleted(tmp_path: Path) -> None:
    path = write(tmp_path, "grep.module.yaml", "old")
    registry = ModuleRegistry([tmp_path])
    registry.scan()
    write(tmp_path, "grep.module.yaml", "new")
    registry.reload(path)
    assert [m.module.summary for m in registry.for_tool("grep")] == ["new"]
    path.write_text("- broken\n")
    registry.reload(path)
    assert registry.for_tool("grep") == []
    assert len(registry.errors) == 1
    path.unlink()
    registry.reload(path)
    assert registry.errors == []
    assert registry.modules == {}


def test_missing_dir_is_fine(tmp_path: Path) -> None:
    registry = ModuleRegistry([tmp_path / "nope"])
    registry.scan()
    assert registry.all() == []
    assert registry.errors == []


def test_reload_relative_and_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    registry = ModuleRegistry([link])
    (real / "a.module.yaml").write_text("schema_version: 1\ntool: a\n")
    registry.reload(link / "a.module.yaml")
    assert registry.for_tool("a")
    monkeypatch.chdir(real)
    (real / "b.module.yaml").write_text("schema_version: 1\ntool: b\n")
    registry.reload(Path("b.module.yaml"))
    assert registry.for_tool("b")
