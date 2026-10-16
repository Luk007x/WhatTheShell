# SPDX-License-Identifier: AGPL-3.0-or-later
"""Discover module files in search directories."""

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from whattheshell.i18n import _
from whattheshell.models.module import Module
from whattheshell.modules.loader import MODULE_SUFFIXES, DocumentError, load_module_file


@dataclass(frozen=True)
class LoadedModule:
    """A validated module with its origin; higher priority wins in the merge chain."""

    path: Path
    module: Module
    priority: int


class ModuleRegistry:
    """All module files of the search directories, grouped by tool; thread-safe."""

    def __init__(self, dirs: Sequence[Path]) -> None:
        self.dirs = [d.resolve() for d in dirs]
        self.modules: dict[str, list[LoadedModule]] = {}
        self.errors: list[DocumentError] = []
        self._lock = threading.Lock()

    def scan(self) -> None:
        """(Re)read every module file; a broken file only lands in ``errors``."""
        modules: dict[str, list[LoadedModule]] = {}
        errors: list[DocumentError] = []
        with self._lock:
            for priority, directory in enumerate(self.dirs):
                if not directory.is_dir():
                    continue
                try:
                    files = sorted(directory.iterdir())
                except OSError as err:
                    errors.append(
                        DocumentError(directory, None, _("Ordner nicht lesbar: {err}", err=err))
                    )
                    continue
                for path in files:
                    if path.name.endswith(MODULE_SUFFIXES):
                        self._add(path, priority, modules, errors)
            self.modules, self.errors = modules, errors

    def reload(self, path: Path) -> None:
        """Reload one file; a deleted file is removed. Files outside ``dirs`` are ignored."""
        path = path.parent.resolve() / path.name
        priority = next((i for i, d in enumerate(self.dirs) if path.parent == d), None)
        if priority is None:
            return
        with self._lock:
            errors = [e for e in self.errors if e.path != path]
            modules = {
                tool: kept
                for tool, items in self.modules.items()
                if (kept := [m for m in items if m.path != path])
            }
            if path.exists():
                self._add(path, priority, modules, errors)
            self.modules, self.errors = modules, errors

    def for_tool(self, tool: str) -> list[LoadedModule]:
        """Modules of a tool in ascending priority."""
        with self._lock:
            return list(self.modules.get(tool, []))

    def all(self) -> list[LoadedModule]:
        """All loaded modules."""
        with self._lock:
            return [m for items in self.modules.values() for m in items]

    @staticmethod
    def _add(
        path: Path,
        priority: int,
        modules: dict[str, list[LoadedModule]],
        errors: list[DocumentError],
    ) -> None:
        try:
            module = load_module_file(path)
        except DocumentError as err:
            errors.append(err)
            return
        items = [*modules.get(module.tool, []), LoadedModule(path, module, priority)]
        modules[module.tool] = sorted(items, key=lambda m: (m.priority, m.path.name))
