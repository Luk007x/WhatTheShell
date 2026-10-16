# SPDX-License-Identifier: AGPL-3.0-or-later
"""Change detection for workflow files: a hash sidecar per folder.

This detects edits made outside the app. It is NOT tamper proofing: anyone who can edit
the file can edit the sidecar too.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from whattheshell import bundled
from whattheshell.modules.store import atomic_write

SIDECAR = ".wts-integrity.json"
Status = Literal["ok", "modified", "unstamped"]
REFUSAL = "Datei wurde außerhalb der App geändert. Prüfen und übernehmen."


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(directory: Path) -> dict[str, dict[str, str]]:
    """Sidecar content; a missing or unreadable sidecar counts as empty (files: unstamped)."""
    try:
        data = json.loads((directory / SIDECAR).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def stamp(path: Path) -> None:
    """Record the current hash of `path` in the sidecar of its folder (0600, atomic).

    Raises:
        OSError: File or sidecar not accessible.
    """
    records = _read(path.parent)
    records[path.name] = {
        "sha256": _digest(path),
        "stamped": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    atomic_write(path.parent / SIDECAR, json.dumps(records, indent=2) + "\n", 0o600)


def status(path: Path) -> Status:
    """Compare `path` with its stamp; bundled files (read-only package data) are always ok.

    Raises:
        OSError: File not readable.
    """
    if path.parent.resolve() == bundled.WORKFLOWS_DIR.resolve():
        return "ok"
    record = _read(path.parent).get(path.name)
    if not isinstance(record, dict) or "sha256" not in record:
        return "unstamped"
    return "ok" if record["sha256"] == _digest(path) else "modified"
