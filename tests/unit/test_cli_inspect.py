# SPDX-License-Identifier: AGPL-3.0-or-later
import json
from pathlib import Path

import pytest

from tests.unit.test_catalog import DEMO, make_tool
from whattheshell.cli import main


@pytest.fixture(autouse=True)
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_tool(tmp_path / "bin", "demo", DEMO)
    make_tool(tmp_path / "bin", "other", DEMO)
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


def test_tools(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["tools"]) == 0
    assert [ln.split("\t")[0] for ln in capsys.readouterr().out.splitlines()] == ["demo", "other"]


def test_tools_search(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["tools", "--search", "DEM"]) == 0
    assert capsys.readouterr().out.startswith("demo\t")


def test_inspect_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", "demo"]) == 0
    out = capsys.readouterr().out
    assert "-a" in out and "-b" in out and "Options:" in out and "interaktiv nein" in out


def test_inspect_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", "demo", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "demo"


def test_inspect_unknown(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", "nope"]) == 1
    assert "nicht auf PATH" in capsys.readouterr().err


def test_inspect_probes_user_typed_subcommand(tmp_path: Path) -> None:
    log = tmp_path / "calls.log"
    make_tool(tmp_path / "bin", "probe", f'#!/bin/sh\necho "$@" >> {log}\necho "Usage: probe"\n')
    assert main(["inspect", "probe", "evil"]) == 0
    assert any(line.startswith("evil") for line in log.read_text().splitlines())
