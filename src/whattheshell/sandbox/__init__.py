# SPDX-License-Identifier: AGPL-3.0-or-later
"""bwrap sandbox for previews. There is deliberately no unsandboxed fallback."""

import logging
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from whattheshell.i18n import _
from whattheshell.subproc import Result, run_limited, sanitized_env

# bwrap cannot create /work on the read-only root, so the workdir lives on the /tmp tmpfs.
WORKDIR_IN_SANDBOX = "/tmp/work"  # noqa: S108
SANDBOX_PATH = "/usr/local/bin:/usr/bin:/bin"
logger = logging.getLogger(__name__)
_HINTS = (
    (("fedora", "rhel", "centos"), "sudo dnf install bubblewrap"),
    (("debian", "ubuntu"), "sudo apt install bubblewrap"),
    (("arch",), "sudo pacman -S bubblewrap"),
    (("opensuse", "suse"), "sudo zypper install bubblewrap"),
    (("alpine",), "sudo apk add bubblewrap"),
)


@dataclass(frozen=True)
class SandboxStatus:
    """Result of the sandbox self test."""

    available: bool
    reason: str
    install_hint: str
    bwrap_path: str | None


def read_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    """Parse os-release into a dict; empty if unreadable."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and not key.startswith("#"):
            values[key.strip()] = value.strip().strip("\"'")
    return values


def install_hint_for_distro(os_release: Mapping[str, str]) -> str:
    """Install command for bubblewrap on the detected distribution."""
    ids = {os_release.get("ID", "").lower(), *os_release.get("ID_LIKE", "").lower().split()}
    for names, hint in _HINTS:
        if ids.intersection(names):
            return hint
    return _("Installiere das Paket „bubblewrap“ über die Paketverwaltung deiner Distribution.")


def _resolv_conf_target() -> str | None:
    """Real file behind a /etc/resolv.conf symlink into /run (hidden by the /run tmpfs)."""
    resolv = Path("/etc/resolv.conf")
    target = os.path.realpath(resolv)
    return target if resolv.is_symlink() and target.startswith("/run/") else None


def build_bwrap_argv(
    argv: Sequence[str],
    workdir: Path,
    *,
    bwrap_path: str,
    env: Mapping[str, str],
    network: bool = False,
) -> list[str]:
    """Full bwrap command line; ``workdir`` is the only writable path."""
    result = [
        bwrap_path,
        *("--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"),
        *("--tmpfs", "/tmp", "--tmpfs", "/var/tmp", "--tmpfs", "/home"),  # noqa: S108
        *("--tmpfs", "/root", "--tmpfs", "/run"),
        *("--bind", str(workdir), WORKDIR_IN_SANDBOX, "--chdir", WORKDIR_IN_SANDBOX),
        *("--unshare-all", "--die-with-parent", "--new-session", "--clearenv"),
        *("--setenv", "HOME", WORKDIR_IN_SANDBOX, "--setenv", "PATH", env["PATH"]),
    ]
    for key, value in env.items():
        if key not in ("HOME", "PATH"):
            result += ["--setenv", key, value]
    if network:
        result.append("--share-net")
        target = _resolv_conf_target()
        if target is not None:  # DNS: only this one file, read-only
            result += ["--ro-bind-try", target, target]
    return [*result, "--", *argv]


def sandbox_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Environment placed inside the sandbox; ``extra`` may override all but PATH."""
    return {
        **sanitized_env(),
        "HOME": WORKDIR_IN_SANDBOX,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        **(extra or {}),
        "PATH": SANDBOX_PATH,
    }


def limited_argv(argv: Sequence[str], memory_bytes: int = 512 * 1024 * 1024) -> list[str]:
    """Prefix ``argv`` with prlimit (address space, process count); warn if prlimit is missing."""
    prlimit = shutil.which("prlimit", path=SANDBOX_PATH)
    if prlimit is None:
        logger.warning("prlimit fehlt: Sandbox läuft ohne Speicher- und Prozesslimit.")
        return list(argv)
    return [prlimit, f"--as={memory_bytes}", "--nproc=256", "--", *argv]


def run_sandboxed(
    argv: Sequence[str],
    workdir: Path,
    *,
    stdin: bytes | None = None,
    timeout: float = 10.0,
    max_bytes: int = 1_048_576,
    memory_bytes: int = 512 * 1024 * 1024,
    env: Mapping[str, str] | None = None,
    bwrap_path: str | None = None,
) -> Result | None:
    """Run ``argv`` inside bwrap with ``workdir`` mounted writable at WORKDIR_IN_SANDBOX.

    Returns None if bwrap is missing or could not be started; never runs unsandboxed.
    """
    bwrap = bwrap_path or shutil.which("bwrap")
    if bwrap is None:
        return None
    return run_limited(
        build_bwrap_argv(
            limited_argv(argv, memory_bytes), workdir, bwrap_path=bwrap, env=sandbox_env(env)
        ),
        timeout=timeout,
        max_bytes=max_bytes,
        stdin=stdin,
    )


def _failure(step: str, result: Result | None, path: str) -> SandboxStatus:
    lines = result.stderr.decode(errors="replace").strip().splitlines() if result else []
    detail = lines[-1] if lines else _("keine Fehlermeldung")
    reason = _(
        "Sandbox-Selbsttest fehlgeschlagen ({step}): {detail} "
        "Prüfe `sysctl kernel.unprivileged_userns_clone` bzw. AppArmor-Einschränkungen.",
        step=step,
        detail=detail,
    )
    return SandboxStatus(False, reason, "", path)


def self_test(bwrap_path: str | None = None) -> SandboxStatus:
    """Check that bwrap works here: runs, isolates writes, network and the root filesystem."""
    path = bwrap_path or shutil.which("bwrap")
    if path is None or not Path(path).exists():
        reason = _("bubblewrap (bwrap) ist nicht installiert.")
        return SandboxStatus(False, reason, install_hint_for_distro(read_os_release()), None)
    with tempfile.TemporaryDirectory(prefix="wts-selftest-") as tmp:
        workdir = Path(tmp)

        def run(argv: list[str]) -> Result | None:
            return run_sandboxed(argv, workdir, timeout=5.0, bwrap_path=path)

        result = run(["/usr/bin/true"])
        if result is None or result.exit_code != 0:
            return _failure(
                _("User-Namespaces sind gesperrt oder bwrap startet nicht"), result, path
            )
        result = run(["/usr/bin/touch", "probe"])
        if result is None or result.exit_code != 0 or not (workdir / "probe").exists():
            return _failure(_("Schreiben im Arbeitsverzeichnis"), result, path)
        if Path("/usr/sbin/ip").exists():
            result = run(["/usr/sbin/ip", "link"])
            if result is None or result.exit_code != 0:
                return _failure(_("Netzwerktest"), result, path)
            names = [
                ln.split(":")[1].strip()
                for ln in result.stdout.decode().splitlines()
                if ln[:1].isdigit()
            ]
            if any(name.split("@")[0] != "lo" for name in names):
                return _failure(_("Netzwerk ist nicht isoliert"), None, path)
        result = run(["/usr/bin/touch", "/etc/wts_probe"])
        if result is None or result.exit_code == 0 or Path("/etc/wts_probe").exists():
            return _failure(_("Schreibschutz des Dateisystems"), result, path)
    reason = (
        ""
        if shutil.which("prlimit")
        else _("prlimit (util-linux) fehlt: keine Speicher-/Prozesslimits.")
    )
    return SandboxStatus(True, reason, "", path)


from whattheshell.sandbox.examples import ExampleResult, iter_examples, run_example  # noqa: E402

__all__ = [
    "SANDBOX_PATH",
    "WORKDIR_IN_SANDBOX",
    "ExampleResult",
    "SandboxStatus",
    "build_bwrap_argv",
    "install_hint_for_distro",
    "iter_examples",
    "limited_argv",
    "read_os_release",
    "run_example",
    "run_sandboxed",
    "sandbox_env",
    "self_test",
]
