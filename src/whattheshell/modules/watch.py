# SPDX-License-Identifier: AGPL-3.0-or-later
"""Live reload of module files while the app runs."""

import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from watchfiles import watch

from whattheshell.modules.loader import MODULE_SUFFIXES
from whattheshell.modules.registry import ModuleRegistry


def _existing_ancestor(directory: Path, floors: Sequence[Path]) -> Path | None:
    """Nearest existing ancestor; None if that would lie above the parent of a `floors` entry
    that `directory` is under (a missing ``.whattheshell`` must not widen the watch to ``/``),
    or if it is the home directory (too large to watch recursively).
    """
    limit = next((f.parent for f in floors if directory.is_relative_to(f)), None)
    while not directory.exists():
        if directory == limit or directory == directory.parent:
            return None
        directory = directory.parent
    return None if directory == Path.home() else directory


def watch_dirs(
    dirs: Sequence[Path],
    suffixes: tuple[str, ...],
    on_change: Callable[[set[Path]], None],
    stop: threading.Event,
    on_start: Callable[[list[tuple[Path, Path]]], None] | None = None,
    floors: Sequence[Path] = (),
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
        floors: Roots (e.g. cwd, config dir); the watch of a missing directory under one of
            them never climbs above that root's parent. Directories that would are skipped.
    """
    pairs = [(d, a) for d in dirs if (a := _existing_ancestor(d, floors)) is not None]
    if not pairs:
        return
    if on_start is not None:
        on_start(pairs)
    # ponytail: recursive watch of the ancestor, can be large (e.g. a project root); narrow if slow
    for changes in watch(
        *{ancestor for _, ancestor in pairs}, stop_event=stop, ignore_permission_denied=True
    ):
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
