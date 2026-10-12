# SPDX-License-Identifier: AGPL-3.0-or-later
"""Index of workflow files in the search directories (bundled < user < project)."""

import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from whattheshell.models.workflow import VariableSpec
from whattheshell.modules.loader import WORKFLOW_SUFFIXES, DocumentError, load_workflow_file

SOURCES = ("bundled", "user", "project")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class WorkflowEntry:
    """One workflow file; a broken file has ``error`` set and ``id`` as ``name``."""

    id: str
    name: str
    description: str | None
    path: Path
    source: str
    variables: dict[str, VariableSpec] = field(default_factory=dict)
    steps: int = 0
    error: str | None = None
    shadows: list[str] = field(default_factory=list)  # sources of same-id files below this one


class WorkflowIndex:
    """Workflows of the search directories by id, highest priority wins; thread-safe."""

    def __init__(self, dirs: Sequence[Path]) -> None:
        self.dirs = [d.resolve() for d in dirs]
        self._entries: dict[str, WorkflowEntry] = {}
        self._lock = threading.Lock()

    def scan(self) -> None:
        """(Re)read every workflow file; a broken file becomes an entry with ``error``."""
        entries: dict[str, WorkflowEntry] = {}
        for source, directory in zip(SOURCES, self.dirs, strict=False):
            if not directory.is_dir():
                continue
            try:
                files = sorted(directory.iterdir())
            except OSError as err:
                entry = WorkflowEntry(
                    directory.name, directory.name, None, directory, source,
                    error=f"{directory}: Ordner nicht lesbar: {err}",
                )  # fmt: skip
                entries[f"{source}:{directory}"] = entry
                continue
            for path in files:
                suffix = next((s for s in WORKFLOW_SUFFIXES if path.name.endswith(s)), None)
                if suffix is None:
                    continue
                entry = _entry(path, path.name.removesuffix(suffix), source)
                below = entries.get(entry.id)
                if below is not None:
                    entry = replace(entry, shadows=[*below.shadows, below.source])
                entries[entry.id] = entry
        with self._lock:
            self._entries = entries

    def reload(self, path: Path) -> None:  # noqa: ARG002 - see ponytail
        """Pick up a changed, new or deleted file."""
        # ponytail: full rescan, shadowing makes a per-file update fiddly; a few files are cheap
        self.scan()

    def all(self) -> list[WorkflowEntry]:
        """All winning entries."""
        with self._lock:
            return list(self._entries.values())

    def get(self, workflow_id: str) -> WorkflowEntry | None:
        """The winning entry of `workflow_id`."""
        with self._lock:
            return self._entries.get(workflow_id)


def _entry(path: Path, workflow_id: str, source: str) -> WorkflowEntry:
    if not ID_PATTERN.fullmatch(workflow_id):
        return WorkflowEntry(
            workflow_id, workflow_id, None, path, source,
            error=f"{path}: Dateiname entspricht nicht dem Muster {ID_PATTERN.pattern}",
        )  # fmt: skip
    try:
        workflow = load_workflow_file(path)
    except DocumentError as err:
        return WorkflowEntry(workflow_id, workflow_id, None, path, source, error=str(err))
    return WorkflowEntry(
        workflow_id,
        workflow.name,
        workflow.description,
        path,
        source,
        workflow.variables,
        len(workflow.steps),
    )
