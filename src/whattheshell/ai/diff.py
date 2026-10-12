# SPDX-License-Identifier: AGPL-3.0-or-later
"""Diff for the approval step."""

import difflib


def unified(old: str | None, new: str, name: str) -> str:
    """Unified diff of `old` (None = new file) against `new`; empty if equal."""
    return "".join(
        difflib.unified_diff(
            (old or "").splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"{name} (aktuell)" if old is not None else "/dev/null",
            tofile=f"{name} (Vorschlag)",
        )
    )
