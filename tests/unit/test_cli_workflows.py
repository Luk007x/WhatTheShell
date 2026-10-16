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
    assert "project\tunstamped\thallo\tHallo\t1\t" in captured.out
    assert "bundled\tok\tlog_errors" in captured.out
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


def test_run_refuses_unstamped_until_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "hallo"]) == 3
    err = capsys.readouterr().err
    assert "außerhalb der App geändert" in err and "wts workflows accept" in err
    assert main(["workflows", "accept", "hallo"]) == 0
    assert main(["run", "hallo"]) == 0
    (Path(".whattheshell/workflows/hallo.workflow.yaml")).write_text(FLOW + "# edit\n")
    assert main(["run", "hallo"]) == 3
    assert main(["run", "hallo", "--accept"]) == 0
    assert main(["run", "hallo"]) == 0


def test_accept_rejects_invalid_and_unknown() -> None:
    assert main(["workflows", "accept", "kaputt"]) == 3
    assert main(["workflows", "accept", "gibt-es-nicht"]) == 1


def test_import_valid_duplicate_overwrite_invalid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "neu.workflow.yaml"
    source.write_text(FLOW)
    assert main(["workflows", "import", str(source)]) == 0
    assert main(["workflows", "import", str(source)]) == 3
    assert "--overwrite" in capsys.readouterr().err
    assert main(["workflows", "import", str(source), "--overwrite"]) == 0
    assert main(["run", "neu"]) == 0  # stamped by the import
    assert main(["workflows"]) == 0
    assert "user\tok\tneu\t" in capsys.readouterr().out
    bad = tmp_path / "bad.workflow.yaml"
    bad.write_text("name: [")
    assert main(["workflows", "import", str(bad)]) == 3
    wrong = tmp_path / "Bad Name.yaml"
    wrong.write_text(FLOW)
    assert main(["workflows", "import", str(wrong)]) == 3


def test_import_refused_when_project_file_shadows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "hallo.workflow.yaml"
    source.write_text(FLOW)
    assert main(["workflows", "import", str(source)]) == 3
    assert "überdeckt" in capsys.readouterr().err
