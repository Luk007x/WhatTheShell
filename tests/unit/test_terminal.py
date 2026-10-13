# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import select
import shutil
import time
from pathlib import Path

import pytest

from whattheshell.terminal import PtyProcess, TerminalUnavailable, spawn

needs_bwrap = pytest.mark.skipif(
    shutil.which("bwrap") is None, reason="bwrap not installed: terminal needs the sandbox"
)


def _read_until(proc: PtyProcess, needle: bytes, timeout: float = 5.0) -> bytes:
    out = b""
    deadline = time.monotonic() + timeout
    while needle not in out and time.monotonic() < deadline:
        if select.select([proc.fd], [], [], 0.1)[0]:
            chunk = proc.read()
            if not chunk:
                break
            out += chunk
    return out


def _start(argv: list[str], workdir: Path) -> PtyProcess:
    return spawn(argv, workdir=workdir, env=None, cols=101, rows=33)


@needs_bwrap
def test_cat_echo(tmp_path: Path) -> None:
    with _start(["cat"], tmp_path) as proc:
        proc.write(b"hi\n")
        assert b"hi" in _read_until(proc, b"hi\r\nhi")


@needs_bwrap
def test_controlling_tty_and_size(tmp_path: Path) -> None:
    with _start(["sh", "-c", "tty; stty size; echo done"], tmp_path) as proc:
        out = _read_until(proc, b"done").decode()
    assert "not a tty" not in out and out.startswith("/dev/")
    assert "33 101" in out


@needs_bwrap
def test_resize_reaches_program(tmp_path: Path) -> None:
    with _start(["sh", "-c", "read x; stty size"], tmp_path) as proc:
        proc.resize(120, 40)
        proc.write(b"\n")
        assert b"40 120" in _read_until(proc, b"40 120")


@needs_bwrap
def test_terminate_kills_group_and_grandchild(tmp_path: Path) -> None:
    proc = _start(["sh", "-c", "sleep 4242 & wait"], tmp_path)
    time.sleep(0.5)
    pgid = os.getpgid(proc.pid)
    proc.terminate()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    with pytest.raises(ProcessLookupError):
        os.killpg(pgid, 0)
    cmdlines = []
    for entry in Path("/proc").iterdir():
        try:
            cmdlines.append((entry / "cmdline").read_bytes())
        except OSError:
            continue
    assert b"sleep\x004242\x00" not in cmdlines
    assert proc.fd == -1


def test_without_bwrap_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda *_a, **_k: None)
    started: list[object] = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: started.append(a))
    with pytest.raises(TerminalUnavailable) as info:
        _start(["cat"], tmp_path)
    assert "bwrap" in info.value.reason and info.value.install_hint
    assert started == []


def test_blocked_env_and_bad_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="LD_PRELOAD"):
        spawn(["cat"], workdir=tmp_path, env={"LD_PRELOAD": "x"}, cols=80, rows=24)
    with pytest.raises(ValueError, match="Terminalgröße"):
        spawn(["cat"], workdir=tmp_path, env=None, cols=0, rows=24)


@needs_bwrap
def test_env_isolated_and_no_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WTS_HOST_SECRET", "leak")
    script = "env; echo net; cut -d: -f1 /proc/net/dev | tail -n +3; echo done"
    with spawn(
        ["sh", "-c", script], workdir=tmp_path, env={"FOO": "bar"}, cols=80, rows=24
    ) as proc:
        out = _read_until(proc, b"done").decode()
    assert "WTS_HOST_SECRET" not in out and "FOO=bar" in out
    assert "TERM=xterm-256color" in out and "HOME=/tmp/work" in out
    assert out.split("\r\nnet\r\n")[1].split() == ["lo", "done"]  # loopback only, as self_test


@needs_bwrap
def test_workdir_writable_home_empty(tmp_path: Path) -> None:
    with _start(["sh", "-c", "touch neu; ls -A /home | wc -l; echo done"], tmp_path) as proc:
        out = _read_until(proc, b"done").decode()
    assert (tmp_path / "neu").exists()
    assert out.split()[0] == "0"
