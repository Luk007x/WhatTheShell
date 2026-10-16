# SPDX-License-Identifier: AGPL-3.0-or-later
"""Heuristic safety classification of commands (pure functions, no I/O)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from whattheshell.i18n import _
from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import Safety

_RANK = (Safety.safe, Safety.caution, Safety.dangerous)


def rank(safety: Safety) -> int:
    """Order of the classes: safe < caution < dangerous."""
    return _RANK.index(safety)


DANGEROUS_TOOLS = frozenset(
    [
        "rm",
        "rmdir",
        "dd",
        "mkfs",
        "shred",
        "wipefs",
        "fdisk",
        "sfdisk",
        "parted",
        "sudo",
        "su",
        "doas",
        "pkexec",
        "chroot",
        "shutdown",
        "reboot",
        "halt",
        "poweroff",
        "kill",
        "killall",
        "pkill",
        "useradd",
        "userdel",
        "usermod",
        "passwd",
        "iptables",
        "nft",
        "mount",
        "umount",
        "losetup",
        "cryptsetup",
        "lvremove",
        "vgremove",
        "pvremove",
        "truncate",
    ]
)
CAUTION_TOOLS = frozenset(
    [
        "mv",
        "cp",
        "chmod",
        "chown",
        "chgrp",
        "tar",
        "rsync",
        "curl",
        "wget",
        "git",
        "pip",
        "pip3",
        "npm",
        "npx",
        "apt",
        "apt-get",
        "dnf",
        "yum",
        "pacman",
        "zypper",
        "brew",
        "docker",
        "podman",
        "ssh",
        "scp",
        "sftp",
        "rclone",
        "xargs",
        "tee",
        "ln",
        "touch",
        "mkdir",
        "install",
        "make",
        "python",
        "python3",
        "node",
        "bash",
        "sh",
        "zsh",
        "perl",
        "ruby",
        "env",
        "nohup",
        "nice",
        "timeout",
        "busybox",
        "setsid",
        "stdbuf",
        "flock",
        "nsenter",
        "systemd-run",
        "script",
        "watch",
        "awk",
        "gawk",
        "mawk",
        "nc",
        "ncat",
        "socat",
    ]
)
# find and sed are caution/safe by default and become dangerous via -delete/-exec/-i below.
_SYSTEMCTL_DANGEROUS = frozenset({"poweroff", "reboot", "halt", "kexec"})

# (flags, tools or None for any tool, resulting class)
_FLAG_RULES: tuple[tuple[frozenset[str], frozenset[str] | None, Safety], ...] = (
    (
        frozenset({"-r", "-R", "--recursive"}),
        frozenset({"chmod", "chown", "chgrp", "rm"}),
        Safety.dangerous,
    ),
    (frozenset({"-r"}), frozenset({"crontab"}), Safety.dangerous),
    (frozenset({"-f", "--force"}), frozenset({"rm", "mv", "cp", "git"}), Safety.caution),
    (
        frozenset(
            {
                "--delete",
                "--remove-source-files",
                "--in-place",
                "--overwrite",
                "--no-preserve-root",
                "-exec",
                "-execdir",
                "-ok",
                "-okdir",
                "-fprint",
                "-fprint0",
                "-fprintf",
                "-fls",
                "-delete",
                "--hard-dereference",
            }
        ),
        None,
        Safety.dangerous,
    ),
    # ponytail: -i only for sed (grep -i is harmless), extend if other in-place tools matter
    (frozenset({"-i"}), frozenset({"sed"}), Safety.dangerous),
    (frozenset({"-o", "--output", "-O"}), frozenset({"curl", "wget"}), Safety.caution),
)


@dataclass(frozen=True)
class Verdict:
    """Safety class of one command with short German reasons."""

    safety: Safety
    reasons: tuple[str, ...]


def _tool_name(spec: CommandSpec) -> str:
    return PurePosixPath(spec.name[0]).name


def _flag_hits(tool: str, flags: Sequence[str]) -> list[tuple[str, Safety]]:
    hits = [
        (flag, safety)
        for rule_flags, tools, safety in _FLAG_RULES
        if tools is None or tool in tools
        for flag in flags
        if flag.partition("=")[0] in rule_flags
    ]
    if tool == "sed":  # -i.bak, -i~ and combined forms; --in-place=SUFFIX is covered above
        hits += [(f, Safety.dangerous) for f in flags if f.startswith("-i") and f != "-i"]
    return hits


def classify_command(
    spec: CommandSpec, args: Mapping[str, object], extra_args: Sequence[str] = ()
) -> Verdict:
    """Classify a command; the highest class of all rules wins.

    Args:
        spec: Command from catalog or module (its ``safety`` is the base).
        args: Option and input values by id; None/False counts as unused.
        extra_args: Free-form arguments, matched by flag text only.

    Returns:
        The resulting class and the reasons for every rule that matched.
    """
    tool = _tool_name(spec)
    safety = spec.safety
    reasons: list[str] = []

    def raise_to(new: Safety, reason: str) -> None:
        nonlocal safety
        reasons.append(reason)
        if rank(new) > rank(safety):
            safety = new

    if tool in DANGEROUS_TOOLS or tool.startswith("mkfs."):
        raise_to(Safety.dangerous, _("Tool {tool} ist gefährlich", tool=tool))
    elif tool in CAUTION_TOOLS:
        raise_to(Safety.caution, _("Tool {tool} erfordert Vorsicht", tool=tool))

    if tool == "systemctl":
        words = {*spec.name[1:], *extra_args, *(v for v in args.values() if isinstance(v, str))}
        if words & _SYSTEMCTL_DANGEROUS:
            raise_to(Safety.dangerous, _("systemctl fährt das System herunter oder startet neu"))

    for option in spec.options:
        if args.get(option.id) in (None, False):
            continue
        if option.safety is not None:
            raise_to(
                option.safety,
                _("Option {id} ist als {safety} eingestuft", id=option.id, safety=option.safety),
            )
        for flag, hit in _flag_hits(tool, option.flags):
            raise_to(hit, _("Option {flag}", flag=flag))

    for flag, hit in _flag_hits(tool, extra_args):
        raise_to(hit, _("Argument {flag}", flag=flag))

    return Verdict(safety, tuple(dict.fromkeys(reasons)))


def summarize(verdicts: Sequence[tuple[str, Verdict]]) -> Safety:
    """Return the highest class of (step id, verdict) pairs; safe if empty."""
    return max((v.safety for _, v in verdicts), key=rank, default=Safety.safe)


def needs_confirmation(safety: Safety) -> bool:
    """Caution and dangerous require explicit confirmation before a real run."""
    return safety is not Safety.safe


def merge_verdicts(first: Verdict, second: Verdict) -> Verdict:
    """Highest class of both, with the reasons of both."""
    safety = max(first.safety, second.safety, key=rank)
    return Verdict(safety, tuple(dict.fromkeys((*first.reasons, *second.reasons))))
