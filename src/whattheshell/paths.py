# SPDX-License-Identifier: AGPL-3.0-or-later
"""Well-known directories of the application."""

import os
from pathlib import Path

from whattheshell import APP_NAME, bundled


def cache_dir() -> Path:
    """Return the cache directory (``$XDG_CACHE_HOME`` or ``~/.cache``); it is not created."""
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / APP_NAME.lower()


def config_dir() -> Path:
    """Return the config directory (``$XDG_CONFIG_HOME`` or ``~/.config``); it is not created."""
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / APP_NAME.lower()


def runtime_dir() -> Path:
    """Return ``$XDG_RUNTIME_DIR/whattheshell`` or ``cache_dir()/run``; it is not created."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    return Path(base) / APP_NAME.lower() if base else cache_dir() / "run"


def module_dirs(project_root: Path | None = None) -> list[Path]:
    """Return module search directories in ascending priority; they may not exist."""
    dirs = [bundled.MODULES_DIR, config_dir() / "modules"]
    if project_root is not None:
        dirs.append(project_root / ".whattheshell" / "modules")
    return dirs


def workflow_dirs(project_root: Path | None = None) -> list[Path]:
    """Return workflow search directories in ascending priority; they may not exist."""
    dirs = [bundled.WORKFLOWS_DIR, config_dir() / "workflows"]
    if project_root is not None:
        dirs.append(project_root / ".whattheshell" / "workflows")
    return dirs


def inside(path: Path, root: Path) -> bool:
    """True if `path` (symlinks and ``..`` resolved) lies within `root`."""
    return path.resolve().is_relative_to(root.resolve())
