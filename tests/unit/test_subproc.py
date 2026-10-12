# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import time
from pathlib import Path

from whattheshell.subproc import run_limited, sanitized_env


def script(tmp_path: Path, body: str) -> str:
    path = tmp_path / "s.sh"
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return str(path)


def test_normal_output(tmp_path: Path) -> None:
    result = run_limited(
        [script(tmp_path, "echo hi; echo err >&2; exit 3")], timeout=5, max_bytes=100
    )
    assert result is not None
    assert (result.stdout, result.stderr, result.exit_code) == (b"hi\n", b"err\n", 3)
    assert not result.timed_out and not result.truncated


def test_timeout_kills_grandchild(tmp_path: Path) -> None:
    pidfile = tmp_path / "pid"
    body = f"sleep 30 &\necho $! > {pidfile}\nsleep 30\n"
    result = run_limited([script(tmp_path, body)], timeout=0.3, max_bytes=100)
    assert result is not None and result.timed_out
    pid = int(pidfile.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)  # zombie until reaped by init
    raise AssertionError("grandchild still alive")


def test_byte_limit(tmp_path: Path) -> None:
    start = time.monotonic()
    result = run_limited(
        [script(tmp_path, "while :; do echo aaaaaaaa; done")], timeout=10, max_bytes=10_000
    )
    assert result is not None and result.truncated
    assert time.monotonic() - start < 2


def test_missing_file(tmp_path: Path) -> None:
    assert run_limited([str(tmp_path / "nope")], timeout=1, max_bytes=10) is None


def test_sanitized_env() -> None:
    assert sanitized_env()["LC_ALL"] == "C"
