# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest

from tests.unit.test_catalog import DEMO, make_tool
from whattheshell import paths
from whattheshell.cli import main

LABELED = (
    "schema_version: 1\ntool: demo\ndisplay_name: Demo-Tool\n"
    "options:\n  - id: a\n    label: Alles zeigen\n"
)


@pytest.fixture
def mod_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_tool(tmp_path / "bin", "demo", DEMO)
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    directory = tmp_path / "mods"
    directory.mkdir()
    monkeypatch.setattr(paths, "module_dirs", lambda root=None: [directory])
    return directory


def test_validate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = tmp_path / "demo.module.yaml"
    good.write_text("schema_version: 1\ntool: demo\n")
    bad = tmp_path / "bad.module.yaml"
    bad.write_text("schema_version: 1\n")
    other = tmp_path / "x.txt"
    other.write_text("")
    assert main(["validate", str(good)]) == 0
    assert f"OK: {good} (Modul demo)" in capsys.readouterr().out
    assert main(["validate", str(good), str(bad), str(other)]) == 1
    captured = capsys.readouterr()
    assert "3 Dateien geprüft, 2 fehlerhaft" in captured.out
    assert str(bad) in captured.err and "Unbekannter Dateityp" in captured.err


def test_scaffold(mod_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scaffold", "demo"]) == 0
    assert "tool: demo" in capsys.readouterr().out
    out = tmp_path / "demo.module.yaml"
    assert main(["scaffold", "demo", "--out", str(out)]) == 0
    assert out.read_text().startswith("# Modul-Gerüst")
    assert main(["validate", str(out)]) == 0
    capsys.readouterr()
    assert main(["scaffold", "demo", "--out", str(out)]) == 1
    assert "--force" in capsys.readouterr().err
    assert main(["scaffold", "demo", "--out", str(out), "--force"]) == 0
    assert main(["scaffold", "nope"]) == 1


def test_modules_lists_and_reports(mod_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (mod_dir / "demo.module.yaml").write_text(LABELED)
    (mod_dir / "bad.module.yaml").write_text("schema_version: 1\n")
    assert main(["modules"]) == 0
    captured = capsys.readouterr()
    assert f"0\tdemo\t{mod_dir / 'demo.module.yaml'}" in captured.out
    assert captured.err.startswith("FEHLER ") and "bad.module.yaml" in captured.err


def test_inspect_with_module(mod_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (mod_dir / "demo.module.yaml").write_text(LABELED)
    assert main(["inspect", "demo"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Demo-Tool (")
    assert f"Module: {mod_dir / 'demo.module.yaml'}" in out
    assert "Alles zeigen: " in out


def test_inspect_broken_module_warns(mod_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (mod_dir / "bad.module.yaml").write_text("schema_version: 1\n")
    assert main(["inspect", "demo"]) == 0
    captured = capsys.readouterr()
    assert captured.err.startswith("WARNUNG ") and "Options:" in captured.out


def test_watch_reports_removed(
    mod_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from whattheshell import cli

    def fake_watch(registry: object, stop: object, on_change: object, on_start: object) -> None:
        assert callable(on_change)
        on_change({mod_dir / "gone.module.yaml"})

    monkeypatch.setattr(cli, "watch_modules", fake_watch)
    assert main(["modules", "--watch"]) == 0
    assert f"entfernt: {mod_dir / 'gone.module.yaml'}" in capsys.readouterr().out


def test_validate_backup_suffix_unknown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "x.module.yaml.bak"
    path.write_text("schema_version: 1\ntool: x\n")
    assert main(["validate", str(path)]) == 1
    assert "Unbekannter Dateityp" in capsys.readouterr().err
