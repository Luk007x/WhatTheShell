# SPDX-License-Identifier: AGPL-3.0-or-later
"""Live reload of module files while the app runs."""

import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from watchfiles import watch

from whattheshell.modules.loader import MODULE_SUFFIXES
from whattheshell.modules.registry import ModuleRegistry


def _existing_ancestor(directory: Path) -> Path:
    while not directory.exists():
        directory = directory.parent
    return directory


def watch_dirs(
    dirs: Sequence[Path],
    suffixes: tuple[str, ...],
    on_change: Callable[[set[Path]], None],
    stop: threading.Event,
    on_start: Callable[[list[tuple[Path, Path]]], None] | None = None,
) -> None:
    """Call ``on_change`` with changed files ending in ``suffixes`` until ``stop`` is set.

    Blocks the calling thread. Missing directories are covered by watching their nearest
    existing ancestor, so a directory created later is picked up.

    Args:
        dirs: Directories to watch.
        suffixes: Only files with one of these endings are reported.
        on_change: Called after each batch with the changed files.
        stop: Setting this event ends the watch.
        on_start: Called once with (directory, watched path) pairs.
    """
    pairs = [(d, _existing_ancestor(d)) for d in dirs]
    if not pairs:
        return
    if on_start is not None:
        on_start(pairs)
    # ponytail: recursive watch of the ancestor, can be large (e.g. a project root); narrow if slow
    for changes in watch(*{ancestor for _, ancestor in pairs}, stop_event=stop):
        paths = {
            Path(p)
            for _, p in changes
            if p.endswith(suffixes) and any(Path(p).is_relative_to(d) for d, _ in pairs)
        }
        if paths:
            on_change(paths)


def watch_modules(
    registry: ModuleRegistry,
    stop: threading.Event,
    on_change: Callable[[set[Path]], None] | None = None,
    on_start: Callable[[list[tuple[Path, Path]]], None] | None = None,
) -> None:
    """Reload changed module files until ``stop`` is set; blocks the calling thread.

    Args:
        registry: Registry whose search directories are watched.
        stop: Setting this event ends the watch.
        on_change: Called after each batch with the changed module files.
        on_start: Called once with (search directory, watched path) pairs.
    """

    def changed(paths: set[Path]) -> None:
        for path in paths:
            registry.reload(path)
        if on_change is not None:
            on_change(paths)

    watch_dirs(registry.dirs, MODULE_SUFFIXES, changed, stop, on_start)
