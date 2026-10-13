# SPDX-License-Identifier: AGPL-3.0-or-later
"""State file of the running GUI instance (``gui.json``), Linux only (``/proc``)."""

import contextlib
import dataclasses
import fcntl
import json
import os
import signal
import time
from pathlib import Path

from whattheshell import paths

STATE_NAME = "gui.json"


@dataclasses.dataclass(frozen=True)
class InstanceInfo:
    """A running ``wts gui`` server."""

    pid: int
    port: int
    url: str
    started: float
    start_ticks: int


def own_start_ticks() -> int:
    """Start time (clock ticks since boot) of this process; 0 without ``/proc``."""
    stat = _proc_stat(os.getpid())
    return stat[1] if stat else 0


def parse_stat(text: str) -> tuple[str, int] | None:
    """Return (state, starttime ticks) from the content of ``/proc/<pid>/stat`` or None."""
    try:
        # the comm field (2) may contain spaces and ")": split after the last ")"
        fields = text.rsplit(")", 1)[1].split()
        return fields[0], int(fields[19])  # fields 3 and 22
    except (IndexError, ValueError):
        return None


def _proc_stat(pid: int) -> tuple[str, int] | None:
    try:
        return parse_stat(Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _proc_cmdline(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    return raw.replace(b"\0", b" ").decode("utf-8", errors="replace").lower()


def state_dir() -> Path:
    """Return the runtime directory, created with mode 0700.

    Raises:
        OSError: If it belongs to someone else or is accessible to others.
    """
    directory = paths.runtime_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise OSError(
            f"{directory} gehört nicht dir oder ist für andere zugänglich. "
            f"Ordner prüfen (chmod 700) oder XDG_RUNTIME_DIR setzen."
        )
    return directory


def acquire_lock() -> int | None:
    """Take the exclusive instance lock for the lifetime of the process.

    Returns:
        The open file descriptor (keep it open), or None if another server holds the lock.
    """
    fd = os.open(state_dir() / "gui.lock", os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def write(info: InstanceInfo) -> Path:
    """Write the state file atomically with mode 0600."""
    target = state_dir() / STATE_NAME
    tmp = target.with_name(f"{STATE_NAME}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(dataclasses.asdict(info), handle)
    tmp.replace(target)
    return target


def read() -> InstanceInfo | None:
    """Return the recorded instance; None if missing, broken or foreign."""
    try:
        data = json.loads((state_dir() / STATE_NAME).read_text(encoding="utf-8"))
        return InstanceInfo(
            pid=int(data["pid"]),
            port=int(data["port"]),
            url=str(data["url"]),
            started=float(data["started"]),
            start_ticks=int(data["start_ticks"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def is_alive(info: InstanceInfo) -> bool:
    """True if `info.pid` is still the same process that wrote the state file."""
    try:
        os.kill(info.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False  # exists, but belongs to someone else
    stat = _proc_stat(info.pid)
    if stat is None:
        return not Path("/proc/self/stat").exists()  # no /proc: kill(0) is all we have
    if stat[0] in ("Z", "X") or stat[1] != info.start_ticks:
        return False
    cmdline = _proc_cmdline(info.pid) or ""
    return "gui" in cmdline and ("whattheshell" in cmdline or "wts" in cmdline)


def clear(info: InstanceInfo) -> None:
    """Delete the state file if it still carries `info.pid`."""
    current = read()
    if current is not None and current.pid == info.pid:
        (state_dir() / STATE_NAME).unlink(missing_ok=True)


def stop(info: InstanceInfo, timeout: float = 15.0) -> bool:
    """SIGTERM, wait up to `timeout` s, then SIGKILL (orphans host runs). True if gone."""
    if not is_alive(info):
        return True
    for sig, wait in ((signal.SIGTERM, timeout), (signal.SIGKILL, 2.0)):
        with contextlib.suppress(ProcessLookupError):
            os.kill(info.pid, sig)
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if not is_alive(info):
                return True
            time.sleep(0.05)
    return not is_alive(info)
