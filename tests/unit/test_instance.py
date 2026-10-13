# SPDX-License-Identifier: AGPL-3.0-or-later
"""State file of the running GUI instance."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from whattheshell import instance
from whattheshell.instance import InstanceInfo


@pytest.fixture(autouse=True)
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(instance, "_proc_cmdline", lambda pid: "python -m whattheshell gui")
    return tmp_path / "whattheshell"


def _own(ticks: int | None = None) -> InstanceInfo:
    start = instance.own_start_ticks() if ticks is None else ticks
    return InstanceInfo(os.getpid(), 1234, "http://127.0.0.1:1234/#token=x", 1.0, start)


def test_roundtrip_mode_0600(runtime: Path) -> None:
    path = instance.write(_own())
    assert path.stat().st_mode & 0o777 == 0o600
    assert runtime.stat().st_mode & 0o777 == 0o700
    assert instance.read() == _own()


def test_read_garbage_is_none(runtime: Path) -> None:
    assert instance.read() is None
    runtime.mkdir(mode=0o700, exist_ok=True)
    (runtime / "gui.json").write_text("{kaputt", encoding="utf-8")
    assert instance.read() is None
    (runtime / "gui.json").write_text('{"pid": "x"}', encoding="utf-8")
    assert instance.read() is None


def test_is_alive() -> None:
    assert instance.is_alive(_own())
    assert not instance.is_alive(_own(ticks=1))  # reused PID
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    assert not instance.is_alive(InstanceInfo(done.pid, 1, "u", 1.0, 1))


def test_clear_only_own(runtime: Path) -> None:
    instance.write(_own())
    instance.clear(InstanceInfo(os.getpid() + 1, 1, "u", 1.0, 1))
    assert instance.read() is not None
    instance.clear(_own())
    assert instance.read() is None


def test_stop_terminates_child() -> None:
    child = subprocess.Popen(["sleep", "60"])
    ticks = instance._proc_stat(child.pid)
    assert ticks is not None
    info = InstanceInfo(child.pid, 1, "u", 1.0, ticks[1])
    assert instance.stop(info, timeout=5.0)
    assert child.wait(timeout=5) == -15
    assert not instance.is_alive(info)


def test_foreign_runtime_dir_rejected(runtime: Path) -> None:
    runtime.mkdir(mode=0o755)
    runtime.chmod(0o755)
    with pytest.raises(OSError, match="chmod 700"):
        instance.write(_own())


def test_parse_stat_comm_with_paren_and_space() -> None:
    rest = " ".join(["S"] + ["0"] * 18 + ["4242"] + ["0"] * 5)
    assert instance.parse_stat(f"1 (we ird) name) {rest}") == ("S", 4242)
    assert instance.parse_stat("garbage") is None


def test_lock_second_holder_loses() -> None:
    first = instance.acquire_lock()
    assert first is not None
    try:
        assert instance.acquire_lock() is None  # flock is per open file description
    finally:
        os.close(first)
    again = instance.acquire_lock()
    assert again is not None
    os.close(again)


def test_stop_falls_back_to_sigkill() -> None:
    code = (
        "import signal,time;signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        "print(1,flush=True);time.sleep(60)"
    )
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
    assert child.stdout is not None
    child.stdout.readline()  # handler installed
    stat = instance._proc_stat(child.pid)
    assert stat is not None
    assert instance.stop(InstanceInfo(child.pid, 1, "u", 1.0, stat[1]), timeout=0.5)
    assert child.wait(timeout=5) == -9


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="needs /proc")
def test_foreground_server_cleans_up(tmp_path: Path) -> None:
    import time

    env = {
        **os.environ,
        "XDG_RUNTIME_DIR": str(tmp_path / "run"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "whattheshell", "gui", "--no-browser", "--port", "0"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state = tmp_path / "run" / "whattheshell" / "gui.json"
    try:
        deadline = time.monotonic() + 30
        while not state.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert state.exists()
        proc.terminate()
        assert proc.wait(timeout=30) == 0
    finally:
        proc.kill()
    assert not state.exists()
    assert not list((tmp_path / "cache").rglob("open-*.html"))
