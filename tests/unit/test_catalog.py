# SPDX-License-Identifier: AGPL-3.0-or-later
import os
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

import pytest

from whattheshell import catalog as catalog_module
from whattheshell.catalog import Catalog, ToolNotFound, scan_path
from whattheshell.catalog import catalog as impl
from whattheshell.catalog.fetch import HelpText, fetch_help

DEMO = """#!/bin/sh
echo "Usage: demo [-a] [-b N]"
echo
echo "  -a  flag"
echo "  -b N  number"
"""
GROUPED = """#!/bin/sh
if [ "$1" = sub ]; then
  echo "Usage: grouped sub [-x]"
  echo
  echo "  -x  extra"
  echo "  -y  other"
else
  echo "Usage: grouped <command>"
  echo
  echo "Commands:"
  echo "  sub  desc"
fi
"""


def make_tool(directory: Path, name: str, body: str, mode: int = 0o755) -> Path:
    directory.mkdir(exist_ok=True)
    path = directory / name
    path.write_text(body)
    path.chmod(mode)
    return path


@pytest.fixture
def bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    make_tool(directory, "demo", DEMO)
    monkeypatch.setenv("PATH", str(directory))
    return directory


@pytest.fixture
def cat(tmp_path: Path) -> Catalog:
    return Catalog(tmp_path / "cache")


def test_scan_path(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    make_tool(first, "dup", "x")
    make_tool(first, "plain", "x", mode=0o644)
    make_tool(second, "dup", "x")
    make_tool(second, "other", "x")
    found = scan_path(os.pathsep.join([str(first), str(tmp_path / "missing"), str(second)]))
    assert [(e.name, e.path) for e in found] == [
        ("dup", str(first / "dup")),
        ("other", str(second / "other")),
    ]


def test_get_parses_and_caches(
    bin_dir: Path, cat: Catalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = cat.get("demo")
    assert info.source == "help"
    assert {f for o in info.command.options for f in o.flags} == {"-a", "-b"}
    assert not info.command.interactive
    assert (cat._cache_dir / "demo.json").exists()

    def boom(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("cache not used")

    monkeypatch.setattr(impl, "fetch_help", boom)
    assert Catalog(cat._cache_dir).get("demo") == info


def test_mtime_change_invalidates(bin_dir: Path, cat: Catalog) -> None:
    cat.get("demo")
    tool = bin_dir / "demo"
    tool.write_text(DEMO.replace("flag", "changed flag"))
    os.utime(tool, ns=(1, 1))
    assert "changed flag" in (cat.get("demo").command.raw_help or "")


def test_refresh_and_broken_cache(
    bin_dir: Path, cat: Catalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    cat.get("demo")
    calls: list[int] = []
    real = fetch_help

    def counting(path: str, subcommand: Sequence[str] = ()) -> HelpText | None:
        calls.append(1)
        return real(path, subcommand)

    monkeypatch.setattr(impl, "fetch_help", counting)
    cat.get("demo")
    assert not calls
    cat.get("demo", refresh=True)
    assert len(calls) == 1
    (cat._cache_dir / "demo.json").write_text("{not json")
    assert cat.get("demo").source == "help"
    assert len(calls) == 2


def test_not_found(bin_dir: Path, cat: Catalog) -> None:
    with pytest.raises(ToolNotFound, match="nicht auf PATH gefunden"):
        cat.get("nope")


def test_fallback(bin_dir: Path, cat: Catalog) -> None:
    make_tool(bin_dir, "silent", "#!/bin/sh\nexit 1\n")
    info = cat.get("silent")
    assert info.source == "fallback"
    assert info.command.confidence == "low"
    assert info.command.name == ["silent"]


def test_interactive(bin_dir: Path, cat: Catalog) -> None:
    make_tool(bin_dir, "vim", DEMO)
    assert cat.get("vim").command.interactive


def test_depth_one(bin_dir: Path, cat: Catalog) -> None:
    make_tool(bin_dir, "grouped", GROUPED)
    assert cat.get("grouped").command.subcommands[0].options == []
    sub = cat.get("grouped", depth=1).command.subcommands[0]
    assert sub.name == ["grouped", "sub"]
    assert {f for o in sub.options for f in o.flags} == {"-x", "-y"}


def test_package_exports() -> None:
    assert "vim" in catalog_module.INTERACTIVE
