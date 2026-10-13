# SPDX-License-Identifier: AGPL-3.0-or-later
import shutil
from pathlib import Path

import pytest

from whattheshell.sandbox import (
    SANDBOX_PATH,
    WORKDIR_IN_SANDBOX,
    build_bwrap_argv,
    install_hint_for_distro,
    run_sandboxed,
    self_test,
)

needs_bwrap = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bwrap not installed")


def test_build_argv_structure(tmp_path: Path) -> None:
    env = {"PATH": "/usr/bin", "LANG": "C"}
    argv = build_bwrap_argv(["echo", "a b"], tmp_path, bwrap_path="/x/bwrap", env=env)
    assert argv[0] == "/x/bwrap"
    assert argv[-3:] == ["--", "echo", "a b"]
    assert "--share-net" not in argv
    assert ["--bind", str(tmp_path), WORKDIR_IN_SANDBOX] == argv[
        argv.index("--bind") : argv.index("--bind") + 3
    ]
    assert argv[argv.index("PATH") - 1 : argv.index("PATH") + 2] == ["--setenv", "PATH", "/usr/bin"]
    assert "--unshare-all" in argv and "--die-with-parent" in argv
    shared = build_bwrap_argv(["x"], tmp_path, bwrap_path="b", env=env, network=True)
    assert "--share-net" in shared


@pytest.mark.parametrize(
    ("os_release", "expected"),
    [
        ({"ID": "fedora"}, "sudo dnf install bubblewrap"),
        ({"ID": "ubuntu", "ID_LIKE": "debian"}, "sudo apt install bubblewrap"),
        ({"ID": "manjaro", "ID_LIKE": "arch"}, "sudo pacman -S bubblewrap"),
        (
            {"ID": "opensuse-tumbleweed", "ID_LIKE": "opensuse suse"},
            "sudo zypper install bubblewrap",
        ),
        ({"ID": "alpine"}, "sudo apk add bubblewrap"),
    ],
)
def test_install_hint(os_release: dict[str, str], expected: str) -> None:
    assert install_hint_for_distro(os_release) == expected


def test_install_hint_unknown() -> None:
    assert "bubblewrap" in install_hint_for_distro({"ID": "plan9"})


def test_self_test_missing_bwrap() -> None:
    status = self_test("/nonexistent")
    assert not status.available and "nicht installiert" in status.reason


@needs_bwrap
def test_self_test_available() -> None:
    status = self_test()
    assert status.available, status.reason


@needs_bwrap
def test_reads_file(tmp_path: Path) -> None:
    (tmp_path / "in.txt").write_text("data")
    result = run_sandboxed(["/usr/bin/cat", "in.txt"], tmp_path)
    assert result is not None and result.stdout == b"data"


@needs_bwrap
def test_read_only_root(tmp_path: Path) -> None:
    result = run_sandboxed(["/usr/bin/touch", "/etc/x"], tmp_path)
    assert result is not None and result.exit_code != 0


@needs_bwrap
def test_workdir_writable(tmp_path: Path) -> None:
    result = run_sandboxed(["/usr/bin/touch", "neu"], tmp_path)
    assert result is not None and result.exit_code == 0
    assert (tmp_path / "neu").exists()


@needs_bwrap
def test_clean_env(tmp_path: Path) -> None:
    result = run_sandboxed(["/usr/bin/sh", "-c", "echo $HOME; env | wc -l"], tmp_path)
    assert result is not None
    home, count = result.stdout.decode().split()
    assert home == WORKDIR_IN_SANDBOX and int(count) < 12


@needs_bwrap
def test_stdin(tmp_path: Path) -> None:
    result = run_sandboxed(["/usr/bin/cat"], tmp_path, stdin=b"hi")
    assert result is not None and result.stdout == b"hi"


@needs_bwrap
@pytest.mark.skipif(shutil.which("curl") is None, reason="curl not installed")
def test_no_network(tmp_path: Path) -> None:
    argv = ["/usr/bin/curl", "-s", "--max-time", "2", "http://127.0.0.1:1/"]
    result = run_sandboxed(argv, tmp_path)
    assert result is not None and result.exit_code != 0


@needs_bwrap
def test_timeout(tmp_path: Path) -> None:
    result = run_sandboxed(["/usr/bin/sleep", "5"], tmp_path, timeout=0.5)
    assert result is not None and result.timed_out


@needs_bwrap
@pytest.mark.skipif(shutil.which("python3") is None, reason="python3 not installed")
def test_memory_limit(tmp_path: Path) -> None:
    result = run_sandboxed(
        ["/usr/bin/python3", "-c", "x = bytearray(900*1024*1024)"],
        tmp_path,
        memory_bytes=512 * 2**20,
    )
    assert result is not None and result.exit_code != 0


@needs_bwrap
def test_nproc_limit_and_fixed_path(tmp_path: Path) -> None:
    # /proc/self/limits statt `ulimit -u`: dash (Ubuntu) kennt -u nicht.
    result = run_sandboxed(
        ["/usr/bin/sh", "-c", "grep 'Max processes' /proc/self/limits; echo $PATH"],
        tmp_path,
        env={"PATH": "/evil"},
    )
    assert result is not None
    lines = result.stdout.decode().splitlines()
    assert lines[0].split()[2:4] == ["256", "256"], lines
    assert lines[-1] == SANDBOX_PATH


def test_resolv_conf_bind_only_with_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "whattheshell.sandbox._resolv_conf_target", lambda: "/run/systemd/resolve/stub-resolv.conf"
    )
    env = {"PATH": "/usr/bin"}
    bind = ["--ro-bind-try", "/run/systemd/resolve/stub-resolv.conf"] * 1
    offline = build_bwrap_argv(["x"], tmp_path, bwrap_path="b", env=env)
    online = build_bwrap_argv(["x"], tmp_path, bwrap_path="b", env=env, network=True)
    assert bind[0] not in offline
    assert online[online.index(bind[0]) :][:3] == [*bind, bind[1]]
    # No real DNS test: the sandbox in CI may have no network, so this stays argv-only.
