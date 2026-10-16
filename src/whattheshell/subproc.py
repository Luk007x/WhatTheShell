# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run an external program with hard time and output limits (argv only, never a shell)."""

import contextlib
import os
import re
import selectors
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import IO

_CHUNK = 65536


def printable(text: str, keep_newlines: bool = False) -> str:
    """Replace control characters (terminal escapes) in foreign text with spaces.

    With `keep_newlines`, line feeds and tabs survive (multi-line text).
    """
    pattern = r"[\x00-\x08\x0b-\x1f\x7f]" if keep_newlines else r"[\x00-\x1f\x7f]"
    return re.sub(pattern, " ", text)


@dataclass(frozen=True)
class Result:
    """Captured output of a limited run."""

    stdout: bytes
    stderr: bytes
    exit_code: int
    timed_out: bool
    truncated: bool
    cancelled: bool = False


def sanitized_env() -> dict[str, str]:
    """Minimal, locale-neutral environment for probing tools."""
    env = {"LC_ALL": "C", "LANG": "C", "COLUMNS": "80", "TERM": "dumb"}
    for key in ("PATH", "HOME"):  # HOME: e.g. podman aborts without it
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):  # already gone
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)


def _feed(pipe: IO[bytes], data: bytes) -> None:
    """Write ``data`` and close; a dead reader (kill, early exit) just ends the thread."""
    with contextlib.suppress(OSError), pipe:  # BrokenPipeError is an OSError
        pipe.write(data)


def run_limited(
    argv: Sequence[str],
    *,
    timeout: float,
    max_bytes: int,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    stdin: bytes | None = None,
    on_chunk: Callable[[str, bytes], None] | None = None,
    cancel: threading.Event | None = None,
) -> Result | None:
    """Run ``argv`` in its own session; kill the whole group on timeout, overflow or cancel.

    Args:
        argv: Program and arguments.
        timeout: Total seconds allowed.
        max_bytes: Limit for stdout and stderr combined.
        env: Environment; defaults to `sanitized_env()`.
        cwd: Working directory.
        stdin: Bytes fed to the program's stdin from a thread; None means /dev/null.
        on_chunk: Called with ("stdout"|"stderr", raw bytes) for every chunk read.
        cancel: When set (checked about every 0.1 s), the group is killed and
            the result has ``cancelled=True``.

    Returns:
        The result, or None if the program could not be started.
    """
    try:
        process = subprocess.Popen(  # noqa: S603
            list(argv),
            stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(sanitized_env() if env is None else env),
            cwd=cwd,
            start_new_session=True,
        )
    except OSError:
        return None
    if stdin is not None:
        assert process.stdin is not None  # noqa: S101
        threading.Thread(target=_feed, args=(process.stdin, stdin), daemon=True).start()
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    total = 0
    timed_out = truncated = cancelled = False
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        assert process.stdout is not None and process.stderr is not None  # noqa: S101
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if cancel is not None and cancel.is_set():
                cancelled = True
                break
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in selector.select(remaining if cancel is None else min(remaining, 0.1)):
                data = os.read(key.fd, _CHUNK)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                chunks[key.data].append(data)
                if on_chunk is not None:
                    on_chunk(key.data, data)
                total += len(data)
            if total > max_bytes:
                truncated = True
                break
    if timed_out or truncated or cancelled:
        _kill_group(process)
    else:
        # ponytail: a daemonised grandchild closing its pipes escapes the group kill
        try:
            process.wait(timeout=max(deadline - time.monotonic(), 0.01))
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(process)
    process.wait()
    process.stdout.close()
    process.stderr.close()
    return Result(
        stdout=b"".join(chunks["stdout"]),
        stderr=b"".join(chunks["stderr"]),
        exit_code=process.returncode,
        timed_out=timed_out,
        truncated=truncated,
        cancelled=cancelled,
    )
