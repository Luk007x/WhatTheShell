# SPDX-License-Identifier: AGPL-3.0-or-later
import json
from pathlib import Path

import pytest

from whattheshell.cli import main

from .test_engine_runner import tools  # noqa: F401

pytestmark = pytest.mark.usefixtures("tools")

SAFE = """schema_version: 1
name: t
steps:
  - { id: a, tool: echo-args, extra_args: ["hello", "world"] }
"""
CAUTION = SAFE + "  - { id: r, tool: git }\n"


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.chdir(tmp_path)


def _file(tmp_path: Path, text: str) -> str:
    path = tmp_path / "t.workflow.yaml"
    path.write_text(text)
    return str(path)


def test_dry_run_prints_plan_and_starts_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", _file(tmp_path, CAUTION), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "echo-args hello world" in out and "caution" in out
    assert not (tmp_path / "counter").exists()


def test_run_live_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", _file(tmp_path, SAFE)]) == 0
    out = capsys.readouterr().out
    assert ">> a (safe): echo-args hello world" in out
    assert "  | hello\n  | world\n" in out and "[ok exit 0" in out and "== success" in out


def test_run_yes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", _file(tmp_path, CAUTION), "--yes", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "success" and data["results"]["a"]["stdout"] == "hello\nworld\n"
    assert data["results"]["a"]["started"].startswith("20")
    assert (tmp_path / "counter").read_text() == "run\n"


def test_caution_without_terminal_needs_yes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", _file(tmp_path, CAUTION)]) == 2
    assert "kein Terminal" in capsys.readouterr().err
    assert not (tmp_path / "counter").exists()


def test_failed_and_aborted_status_codes(tmp_path: Path) -> None:
    failing = "schema_version: 1\nname: t\nsteps:\n  - { id: f, tool: fail }\n"
    stopping = "schema_version: 1\nname: t\nsteps:\n  - { id: s, kind: abort, text: stop }\n"
    assert main(["run", _file(tmp_path, failing)]) == 1
    assert main(["run", _file(tmp_path, stopping)]) == 2


def test_document_error_is_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.workflow.yaml"
    bad.write_text("schema_version: 1\nname: t\nsteps: [{id: a}]\n")
    assert main(["run", str(bad)]) == 3
    assert "bad.workflow.yaml" in capsys.readouterr().err
    assert main(["run", str(tmp_path / "missing.workflow.yaml")]) == 3


def test_prepare_and_var_errors_are_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    unknown = "schema_version: 1\nname: t\nsteps:\n  - { id: a, tool: no-such-tool-wts }\n"
    assert main(["run", _file(tmp_path, unknown)]) == 3
    assert "nicht auf PATH" in capsys.readouterr().err
    assert main(["run", _file(tmp_path, SAFE), "--var", "novalue"]) == 3
    assert main(["run", _file(tmp_path, SAFE), "--var", "x=1"]) == 3


def test_json_output_has_no_secret(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = (
        "schema_version: 1\nname: t\nvariables:\n  pw: { type: secret, required: true }\n"
        'steps:\n  - { id: a, tool: echo-args, extra_args: ["{{ var.pw }}", "x{{ var.pw }}"] }\n'
    )
    assert main(["run", _file(tmp_path, text), "--var", 'pw=h"unter2', "--json", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "unter2" not in out and json.loads(out)["variables"] == {"pw": "***"}


TERMINAL = "schema_version: 1\nname: t\nsteps:\n  - { id: t, kind: terminal, tool: echo-args }\n"


def test_terminal_workflow_is_refused_but_dry_run_shows_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", _file(tmp_path, TERMINAL), "--dry-run"]) == 0
    assert "[terminal] interaktiv" in capsys.readouterr().out
    assert main(["run", _file(tmp_path, TERMINAL), "--yes"]) != 0
    assert "nur in `wts gui`" in capsys.readouterr().err
