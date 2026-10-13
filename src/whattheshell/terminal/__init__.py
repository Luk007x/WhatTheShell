# SPDX-License-Identifier: AGPL-3.0-or-later
"""Interactive program on a PTY, always inside bwrap (SECURITY.md 7.2). No logging here."""

import contextlib
import fcntl
import os
import select
import shutil
import signal
import struct
import subprocess
import termios
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import TracebackType

from whattheshell.sandbox import SANDBOX_PATH, WORKDIR_IN_SANDBOX, build_bwrap_argv, self_test
from whattheshell.subproc import _kill_group, sanitized_env

_HANGUP_GRACE = 2.0
_WRITE_TIMEOUT = 5.0
_MEMORY_BYTES = 512 * 1024 * 1024  # as run_sandboxed


class TerminalUnavailable(Exception):  # noqa: N818 - name fixed by the contract
    """No sandboxed terminal possible here; ``install_hint`` says how to fix it."""

    def __init__(self, reason: str, install_hint: str) -> None:
        super().__init__(f"{reason} {install_hint}".strip())
        self.reason = reason
        self.install_hint = install_hint


def _winsize(cols: int, rows: int) -> bytes:
    if not (0 < cols < 65536 and 0 < rows < 65536):
        raise ValueError(f"Ungültige Terminalgröße {cols}x{rows}: erlaubt sind 1 bis 65535.")
    return struct.pack("HHHH", rows, cols, 0, 0)


class PtyProcess:
    """Sandboxed process attached to a PTY; ``fd`` is the non-blocking master side."""

    def __init__(self, process: subprocess.Popen[bytes], master: int) -> None:
        self._process = process
        self.fd = master
        self.pid = process.pid

    def fileno(self) -> int:
        return self.fd

    def read(self, max_bytes: int = 65536) -> bytes:
        """Available output; b"" once the program side is closed.

        Raises BlockingIOError when nothing is ready (wait with asyncio ``add_reader``).
        """
        try:
            return os.read(self.fd, max_bytes)
        except OSError as exc:
            if isinstance(exc, BlockingIOError):
                raise
            return b""  # EIO: every slave fd is closed, i.e. end of output

    def write(self, data: bytes) -> None:
        """Write all of ``data`` (keystrokes); TimeoutError if the program never reads."""
        view = memoryview(data)
        while view:
            try:
                view = view[os.write(self.fd, view) :]
            except BlockingIOError:
                if not select.select([], [self.fd], [], _WRITE_TIMEOUT)[1]:
                    raise TimeoutError("Terminal nimmt keine Eingaben an.") from None

    def resize(self, cols: int, rows: int) -> None:
        """Set the window size; the kernel sends SIGWINCH to the foreground program."""
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, _winsize(cols, rows))

    def poll(self) -> int | None:
        return self._process.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self._process.wait(timeout)

    def terminate(self) -> None:
        """SIGHUP to the group, SIGKILL after 2 s; bwrap then tears down the PID namespace."""
        if self._process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.pid, signal.SIGHUP)
            try:
                self._process.wait(_HANGUP_GRACE)
            except subprocess.TimeoutExpired:
                _kill_group(self._process)
                self._process.wait()
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> "PtyProcess":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.terminate()


def spawn(
    argv: Sequence[str],
    *,
    workdir: Path,
    env: Mapping[str, str] | None,
    cols: int,
    rows: int,
    network: bool = False,
    bwrap_path: str | None = None,
) -> PtyProcess:
    """Start ``argv`` in bwrap with a PTY as controlling terminal; ``workdir`` is writable.

    Raises TerminalUnavailable without a working bwrap or ``setsid``, ValueError for a bad
    size, an empty argv, a missing workdir or a blocked environment key.
    """
    # Lazy: engine will import this module for terminal steps (avoid an import cycle).
    from whattheshell.engine.runner import env_blocked

    size = _winsize(cols, rows)
    if not argv:
        raise ValueError("Kein Programm angegeben.")
    if not workdir.is_dir():
        raise ValueError(f"Arbeitsverzeichnis {workdir} fehlt. Ordner anlegen oder cwd ändern.")
    blocked = sorted(key for key in env or {} if env_blocked(key))
    if blocked:
        raise ValueError(f"Umgebungsvariablen nicht erlaubt: {', '.join(blocked)}.")
    status = self_test(bwrap_path)
    if not status.available or status.bwrap_path is None:
        raise TerminalUnavailable(status.reason, status.install_hint)
    setsid = shutil.which("setsid")
    if setsid is None:
        raise TerminalUnavailable("setsid fehlt.", "Installiere das Paket „util-linux“.")
    full_env = {
        **sanitized_env(),
        "TERM": "xterm-256color",
        "COLUMNS": str(cols),
        "LINES": str(rows),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": WORKDIR_IN_SANDBOX,
        **(env or {}),
        "PATH": SANDBOX_PATH,
    }
    prlimit = shutil.which("prlimit")  # missing: self_test already reports it in its reason
    limit = [] if prlimit is None else [prlimit, f"--as={_MEMORY_BYTES}", "--nproc=256", "--"]
    # bwrap --new-session stays (TIOCSTI); setsid --ctty makes the PTY the controlling tty.
    inner = [setsid, "--ctty", *limit, *argv]
    master, slave = os.openpty()
    try:
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)
        process = subprocess.Popen(  # noqa: S603
            build_bwrap_argv(
                inner, workdir, bwrap_path=status.bwrap_path, env=full_env, network=network
            ),
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=full_env,
            start_new_session=True,
        )
    except OSError as exc:
        os.close(master)
        raise TerminalUnavailable(f"bwrap startet nicht: {exc}.", "") from exc
    finally:
        os.close(slave)
    os.set_blocking(master, False)
    return PtyProcess(process, master)


__all__ = ["PtyProcess", "TerminalUnavailable", "spawn"]
