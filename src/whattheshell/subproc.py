# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run an external program with hard time and output limits (argv only, never a shell)."""

import contextlib
import os
import selectors
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_CHUNK = 65536


@dataclass(frozen=True)
class Result:
    """Captured output of a limited run."""

    stdout: bytes
    stderr: bytes
    exit_code: int
    timed_out: bool
    truncated: bool


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


def run_limited(
    argv: Sequence[str],
    *,
    timeout: float,
    max_bytes: int,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
) -> Result | None:
    """Run ``argv`` in its own session; kill the whole group on timeout or output overflow.

    Args:
        argv: Program and arguments.
        timeout: Total seconds allowed.
        max_bytes: Limit for stdout and stderr combined.
        env: Environment; defaults to `sanitized_env()`.
        cwd: Working directory.

    Returns:
        The result, or None if the program could not be started.
    """
    try:
        process = subprocess.Popen(  # noqa: S603
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(sanitized_env() if env is None else env),
            cwd=cwd,
            start_new_session=True,
        )
    except OSError:
        return None
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    total = 0
    timed_out = truncated = False
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        assert process.stdout is not None and process.stderr is not None  # noqa: S101
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in selector.select(remaining):
                data = os.read(key.fd, _CHUNK)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                chunks[key.data].append(data)
                total += len(data)
            if total > max_bytes:
                truncated = True
                break
    if timed_out or truncated:
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
    )
