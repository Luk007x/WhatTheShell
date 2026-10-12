# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest

from whattheshell.cli import main

from .test_engine_runner import tools  # noqa: F401

pytestmark = pytest.mark.usefixtures("tools")

FLOW = "schema_version: 1\nname: Hallo\nsteps:\n  - { id: a, tool: echo-args, extra_args: [hi] }\n"


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / ".whattheshell" / "workflows"
    folder.mkdir(parents=True)
    (folder / "hallo.workflow.yaml").write_text(FLOW)
    (folder / "kaputt.workflow.yaml").write_text("name: [")


def test_list_shows_sources_and_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["workflows"]) == 0
    captured = capsys.readouterr()
    assert "project\thallo\tHallo\t1\t" in captured.out
    assert "bundled\tlog_errors" in captured.out
    assert "FEHLER" in captured.err and "kaputt.workflow.yaml" in captured.err


def test_run_by_id(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "hallo", "--dry-run"]) == 0
    assert "echo-args hi" in capsys.readouterr().out


def test_run_unknown_id_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "gibt-es-nicht", "--dry-run"]) == 3


def test_run_by_id_names_the_source(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "hallo", "--dry-run"]) == 0
    assert "Quelle project:" in capsys.readouterr().err


def test_existing_non_workflow_path_hints_at_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "hallo").mkdir()
    assert main(["run", "hallo", "--dry-run"]) == 3
    assert "Vorrang vor der Workflow-id" in capsys.readouterr().err
