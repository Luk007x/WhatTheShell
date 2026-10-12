# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import threading
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


def test_stdin_passed(tmp_path: Path) -> None:
    result = run_limited(["/usr/bin/cat"], timeout=5, max_bytes=100, stdin=b"hello")
    assert result is not None and result.stdout == b"hello"


def test_large_stdin_filter_does_not_deadlock() -> None:
    data = b"x" * 300_000
    start = time.monotonic()
    result = run_limited(["/usr/bin/cat"], timeout=5, max_bytes=1_000_000, stdin=data)
    assert result is not None and result.stdout == data
    assert time.monotonic() - start < 2


def test_large_stdin_timeout() -> None:
    start = time.monotonic()
    result = run_limited(["/usr/bin/sleep", "5"], timeout=0.5, max_bytes=100, stdin=b"x" * 300_000)
    assert result is not None and result.timed_out
    assert time.monotonic() - start < 2


def test_on_chunk_receives_raw_bytes_per_stream(tmp_path: Path) -> None:
    seen: list[tuple[str, bytes]] = []
    result = run_limited(
        [script(tmp_path, "printf out; printf err >&2")],
        timeout=5,
        max_bytes=100,
        on_chunk=lambda stream, data: seen.append((stream, data)),
    )
    assert result is not None and not result.cancelled
    assert sorted(seen) == [("stderr", b"err"), ("stdout", b"out")]


def test_cancel_kills_process_group(tmp_path: Path) -> None:
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    start = time.monotonic()
    result = run_limited([script(tmp_path, "sleep 30")], timeout=60, max_bytes=100, cancel=cancel)
    assert result is not None and result.cancelled and not result.timed_out
    assert time.monotonic() - start < 2
