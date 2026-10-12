# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fetch help text of an installed tool (``--help``, ``-h``, ``man``)."""

import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from whattheshell.helpparse import clean_text
from whattheshell.subproc import run_limited

NEVER_PROBE = frozenset({"shutdown", "reboot", "halt", "poweroff", "init", "telinit", "kexec"})


@dataclass(frozen=True)
class HelpText:
    """Cleaned help text and where it came from."""

    text: str
    source: Literal["help", "h", "man"]
    exit_code: int


def _is_help(text: str) -> bool:
    """A help text has at least 3 non-empty lines and mentions usage or an option line."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    return "usage" in text.lower() or any(line.lstrip().startswith("-") for line in lines)


def fetch_help(
    path: str,
    subcommand: Sequence[str] = (),
    *,
    timeout: float = 5.0,
    max_bytes: int = 1_000_000,
) -> HelpText | None:
    """Run the tool's help and return the first usable output.

    Tries ``--help``, ``-h`` and (without subcommand) ``man -P cat``.

    Args:
        path: Executable to probe.
        subcommand: Subcommand words inserted before the help flag.
        timeout: Seconds per attempt; a timed-out attempt counts as failed.
        max_bytes: Output is cut off after this many bytes.

    Returns:
        The help text, or None if nothing usable came back, the tool (or its symlink
        target) is on `NEVER_PROBE`, or it cannot be executed.
    """
    base = os.path.basename(path)
    if NEVER_PROBE & {base, os.path.basename(os.path.realpath(path))}:
        return None
    attempts: list[tuple[list[str], Literal["help", "h", "man"]]] = [
        ([path, *subcommand, "--help"], "help"),
        ([path, *subcommand, "-h"], "h"),
    ]
    if not subcommand and shutil.which("man"):
        attempts.append((["man", "-P", "cat", "--", base], "man"))
    for argv, source in attempts:
        done = run_limited(argv, timeout=timeout, max_bytes=max_bytes)
        if done is None:
            if source == "man":
                continue
            return None
        if done.timed_out:
            continue
        for stream in (done.stdout, done.stderr):
            text = clean_text(stream[:max_bytes].decode("utf-8", errors="replace"))
            if _is_help(text):
                return HelpText(text=text, source=source, exit_code=done.exit_code)
    return None
