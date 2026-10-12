# SPDX-License-Identifier: AGPL-3.0-or-later
"""Well-known directories of the application."""

import os
from pathlib import Path

from whattheshell import APP_NAME


def cache_dir() -> Path:
    """Return the cache directory (``$XDG_CACHE_HOME`` or ``~/.cache``); it is not created."""
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / APP_NAME.lower()
