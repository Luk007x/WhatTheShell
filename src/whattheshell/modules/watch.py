# SPDX-License-Identifier: AGPL-3.0-or-later
"""Live reload of module files while the app runs."""

import threading
from collections.abc import Callable
from pathlib import Path

from watchfiles import watch

from whattheshell.modules.loader import MODULE_SUFFIXES
from whattheshell.modules.registry import ModuleRegistry


def _existing_ancestor(directory: Path) -> Path:
    while not directory.exists():
        directory = directory.parent
    return directory


def watch_modules(
    registry: ModuleRegistry,
    stop: threading.Event,
    on_change: Callable[[set[Path]], None] | None = None,
    on_start: Callable[[list[tuple[Path, Path]]], None] | None = None,
) -> None:
    """Reload changed module files until ``stop`` is set; blocks the calling thread.

    Missing directories are covered by watching their nearest existing ancestor,
    so a directory created later is picked up.

    Args:
        registry: Registry whose search directories are watched.
        stop: Setting this event ends the watch.
        on_change: Called after each batch with the changed module files.
        on_start: Called once with (search directory, watched path) pairs.
    """
    pairs = [(d, _existing_ancestor(d)) for d in registry.dirs]
    if not pairs:
        return
    if on_start is not None:
        on_start(pairs)
    # ponytail: recursive watch of the ancestor, can be large (e.g. a project root); narrow if slow
    for changes in watch(*{ancestor for _, ancestor in pairs}, stop_event=stop):
        paths = {
            Path(p)
            for _, p in changes
            if p.endswith(MODULE_SUFFIXES) and any(Path(p).is_relative_to(d) for d, _ in pairs)
        }
        if not paths:
            continue
        for path in paths:
            registry.reload(path)
        if on_change is not None:
            on_change(paths)
