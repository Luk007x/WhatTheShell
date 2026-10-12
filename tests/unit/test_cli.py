# SPDX-License-Identifier: AGPL-3.0-or-later
import sys
from pathlib import Path

import pytest

from whattheshell import APP_NAME
from whattheshell.cli import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert APP_NAME in capsys.readouterr().out


def test_no_command_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out


def test_broken_pipe_is_not_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = tmp_path / "bin" / "demo"
    tool.parent.mkdir()
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", str(tool.parent))

    class ClosedPipe:
        def __init__(self, fileno: int) -> None:
            self._fileno = fileno

        def write(self, text: str) -> int:
            raise BrokenPipeError

        def flush(self) -> None:
            pass

        def fileno(self) -> int:
            return self._fileno

    with (tmp_path / "sink").open("w") as sink:
        monkeypatch.setattr(sys, "stdout", ClosedPipe(sink.fileno()))
        assert main(["tools"]) == 0
