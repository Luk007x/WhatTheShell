# SPDX-License-Identifier: AGPL-3.0-or-later
import shutil
from pathlib import Path

import pytest

from whattheshell import cli
from whattheshell.cli import main
from whattheshell.sandbox import ExampleResult, SandboxStatus, self_test

needs_sandbox = pytest.mark.skipif(
    not self_test().available or shutil.which("wc") is None, reason="Sandbox oder wc fehlt"
)
UNAVAILABLE = SandboxStatus(False, "bwrap fehlt", "sudo dnf install bubblewrap", None)


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.chdir(tmp_path)


def test_sandbox_unavailable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "self_test", lambda: UNAVAILABLE)
    assert main(["sandbox"]) == 1
    out = capsys.readouterr().out
    assert "Sandbox nicht verfügbar: bwrap fehlt" in out
    assert "Installieren: sudo dnf install bubblewrap" in out


def test_sandbox_available(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "self_test", lambda: SandboxStatus(True, "", "", "/usr/bin/bwrap"))
    assert main(["sandbox"]) == 0
    assert "Sandbox verfügbar: /usr/bin/bwrap" in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("wc") is None, reason="wc fehlt")
def test_example_without_sandbox_is_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "self_test", lambda: UNAVAILABLE)
    assert main(["example", "wc"]) == 2
    assert "Installieren:" in capsys.readouterr().err


@pytest.mark.skipif(shutil.which("wc") is None, reason="wc fehlt")
def test_example_output_and_failure_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "self_test", lambda: SandboxStatus(True, "", "", "/x"))

    def fake(info: object, example: object, *, status: object) -> ExampleResult:
        return ExampleResult("wc", "T", "wc -l a", 1, "out\n", "err\n", 0.01, ("kaputt",), None)

    monkeypatch.setattr(cli, "run_example", fake)
    assert main(["example", "wc", "1"]) == 1
    out = capsys.readouterr().out
    assert (
        "Beispiel 1: T\n  $ wc -l a\n  | out\n  ! err\n  [FEHLER exit 1, 0.01s]\n  -> kaputt" in out
    )
    assert main(["example", "wc", "99"]) == 3


@needs_sandbox
def test_example_real_sandbox(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["example", "wc", "1"]) == 0
    out = capsys.readouterr().out
    assert "Beispiel 1: Zeilen zählen" in out and "  [ok exit 0" in out
