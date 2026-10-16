# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module and workflow text: validate it, and write user files safely (single write path)."""

import os
import re
import tempfile
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel

from whattheshell import paths
from whattheshell.i18n import _
from whattheshell.models.module import Module
from whattheshell.models.workflow import Workflow
from whattheshell.modules.loader import (
    MODULE_SUFFIXES,
    WORKFLOW_SUFFIXES,
    DocumentError,
    load_document,
)
from whattheshell.modules.registry import ModuleRegistry

Kind = Literal["module", "workflow"]
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
IMPORT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*\.workflow\.yaml$")  # id + suffix, no path
MAX_IMPORT_BYTES = 1024 * 1024
T = TypeVar("T", bound=BaseModel)


def user_dir(kind: Kind) -> Path:
    """The only folder AI results and the editor write to."""
    return paths.config_dir() / ("modules" if kind == "module" else "workflows")


def _load_text(raw: str, model: type[T], filename: str) -> T:
    with tempfile.TemporaryDirectory(prefix="wts-text-") as tmp:
        path = Path(tmp) / filename
        path.write_text(raw, encoding="utf-8")
        return load_document(path, model)


def load_module_text(raw: str) -> Module:
    """Validate module text like a file.

    Raises:
        DocumentError: Syntax or schema violation (``path`` is a temporary file name).
    """
    return _load_text(raw, Module, "text.module.yaml")


def load_workflow_text(raw: str) -> Workflow:
    """Validate workflow text like a file.

    Raises:
        DocumentError: Syntax or schema violation.
    """
    return _load_text(raw, Workflow, "text.workflow.yaml")


def _lines(err: DocumentError) -> list[str]:
    where = _("Zeile {line}: ", line=err.line) if err.line is not None else ""
    return [f"{where}{err.message.strip()}"]


def validate_module_text(raw: str) -> tuple[Module | None, list[str]]:
    """Module or error lines."""
    try:
        return load_module_text(raw), []
    except DocumentError as err:
        return None, _lines(err)


def validate_workflow_text(raw: str) -> tuple[Workflow | None, list[str]]:
    """Workflow or error lines."""
    try:
        return load_workflow_text(raw), []
    except DocumentError as err:
        return None, _lines(err)


def user_path(kind: Kind, name: str) -> Path:
    """Path of a user file.

    Raises:
        ValueError: `name` is not a plain file name with the suffix of `kind`.
    """
    suffixes = MODULE_SUFFIXES if kind == "module" else WORKFLOW_SUFFIXES
    if not NAME.fullmatch(name) or not name.endswith(suffixes):
        raise ValueError(
            _(
                "Ungültiger Dateiname '{name}', erwartet z. B. name{suffix}",
                name=name,
                suffix=suffixes[0],
            )
        )
    return user_dir(kind) / name


def atomic_write(path: Path, text: str, mode: int) -> None:
    """Write via private temp file and rename: no half file, a symlink at `path` is replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_user_file(kind: Kind, name: str, raw: str) -> Path:
    """Write `raw` (mode 0600) into the user's module or workflow folder; workflows get stamped.

    Raises:
        ValueError: Bad `name`.
        OSError: Not writable.
    """
    target = user_path(kind, name)
    atomic_write(target, raw, 0o600)
    if kind == "workflow":
        from whattheshell import integrity  # late: integrity itself uses atomic_write

        integrity.stamp(target)
    return target


def registry_module_text(tool: str, registry: ModuleRegistry) -> str | None:
    """Raw text of the effective module of `tool` (highest priority), None if there is none.

    Raises:
        OSError: The file is not readable.
    """
    loaded = registry.for_tool(tool)
    return loaded[-1].path.read_text(encoding="utf-8") if loaded else None
