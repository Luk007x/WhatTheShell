# SPDX-License-Identifier: AGPL-3.0-or-later
"""Clean terminal help output."""

import re

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
_OVERSTRIKE_RE = re.compile(r".\x08")


def clean_text(raw: str) -> str:
    """Remove terminal control sequences and normalise whitespace.

    Strips ANSI escapes, backspace overstrike (``x\\bx``, ``_\\bx``) and ``\\r``,
    expands tabs to 8 columns and normalises line endings.
    """
    text = _ANSI_RE.sub("", raw)
    text = _OVERSTRIKE_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "")
    return "\n".join(line.rstrip() for line in text.expandtabs(8).split("\n"))
