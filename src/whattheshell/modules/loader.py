# SPDX-License-Identifier: AGPL-3.0-or-later
"""Load and validate one module or workflow file."""

import json
import stat
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from whattheshell.models.migrate import MigrationError, migrate
from whattheshell.models.module import Module
from whattheshell.models.validation import format_validation_error
from whattheshell.models.workflow import Workflow

MODULE_SUFFIXES = (".module.yaml", ".module.yml", ".module.json")
WORKFLOW_SUFFIXES = (".workflow.yaml", ".workflow.yml", ".workflow.json")

MAX_DOCUMENT_BYTES = 1_048_576

T = TypeVar("T", bound=BaseModel)


class DocumentError(Exception):
    """A module or workflow file cannot be used; deactivates only that file."""

    def __init__(self, path: Path, line: int | None, message: str) -> None:
        super().__init__(path, line, message)
        self.path = path
        self.line = line
        self.message = message

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line is not None else f"{self.path}"
        return f"{where}: {self.message}"


def _plain(node: Any, seen: set[int] | None = None) -> Any:
    """Convert a ruamel round-trip tree into plain dict/list/scalars.

    Raises:
        ValueError: A container is reachable twice (YAML alias).
    """
    seen = set() if seen is None else seen
    if isinstance(node, dict | list):
        if id(node) in seen:
            raise ValueError("YAML-Aliase (&anker/*alias) sind nicht erlaubt")
        seen.add(id(node))
    if isinstance(node, dict):
        return {_plain(k, seen): _plain(v, seen) for k, v in node.items()}
    if isinstance(node, list):
        return [_plain(v, seen) for v in node]
    if isinstance(node, bool):
        return bool(node)
    if isinstance(node, int):
        return int(node)
    if isinstance(node, float):
        return float(node)
    if isinstance(node, str):
        return str(node)
    return node


def _line_of(doc: Any, loc: tuple[int | str, ...]) -> int | None:
    """Best-effort 1-based line of a field path; the deepest existing node wins."""
    line: int | None = None
    node = doc
    for part in loc:
        if isinstance(node, CommentedMap) and part in node:
            line = node.lc.key(part)[0] + 1
        elif isinstance(node, CommentedSeq) and isinstance(part, int) and part < len(node):
            line = node.lc.item(part)[0] + 1
        else:
            break
        node = node[part]
    return line


def load_document(path: Path, model: type[T], *, show_input: bool = True) -> T:
    """Read, migrate and validate a YAML or JSON document against a model.

    Args:
        path: File to read; JSON if it ends in ``.json``, else YAML.
        model: Pydantic model the document must satisfy.
        show_input: Append the offending input to schema errors; False for data that may hold
            secrets.

    Returns:
        The validated model instance.

    Raises:
        DocumentError: Unreadable file, syntax error, wrong structure or
            schema violation (with line where known).
    """
    try:
        return _load(path, model, show_input)
    except RecursionError as err:
        raise DocumentError(path, None, "Dokument zu tief verschachtelt") from err
    except MemoryError as err:
        raise DocumentError(path, None, "Speichergrenze überschritten") from err


def _load(path: Path, model: type[T], show_input: bool) -> T:
    try:
        if not stat.S_ISREG(path.stat().st_mode):  # follows symlinks; FIFO/device would hang
            raise DocumentError(path, None, "Keine reguläre Datei")
        with path.open("rb") as handle:
            data = handle.read(MAX_DOCUMENT_BYTES + 1)
        if len(data) > MAX_DOCUMENT_BYTES:
            raise DocumentError(path, None, "Datei zu groß (Grenze 1 MiB)")
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as err:
        raise DocumentError(path, None, f"Datei nicht lesbar: {err}") from err

    doc: Any
    try:
        doc = json.loads(text) if path.suffix == ".json" else YAML(typ="rt").load(text)
    except json.JSONDecodeError as err:
        raise DocumentError(path, err.lineno, f"Ungültiges JSON: {err.msg}") from err
    except YAMLError as err:
        mark = getattr(err, "problem_mark", None)
        problem = getattr(err, "problem", None) or str(err)
        raise DocumentError(
            path, mark.line + 1 if mark else None, f"Ungültiges YAML: {problem}"
        ) from err

    try:
        migrated = migrate(doc)
    except MigrationError as err:
        raise DocumentError(path, None, str(err)) from err
    try:
        plain = _plain(migrated)
    except ValueError as err:
        raise DocumentError(path, None, str(err)) from err
    try:
        return model.model_validate(plain)
    except ValidationError as err:
        first = err.errors()[0]["loc"] if err.errors() else ()
        raise DocumentError(
            path,
            _line_of(migrated, first),
            "\n" + format_validation_error(err, show_input=show_input),
        ) from err


def load_module_file(path: Path) -> Module:
    """Load a ``*.module.yaml|yml|json`` file.

    Raises:
        DocumentError: Bad file name or any error of `load_document`.
    """
    if not path.name.endswith(MODULE_SUFFIXES):
        raise DocumentError(path, None, "Dateiname muss auf .module.yaml enden")
    return load_document(path, Module)


def load_workflow_file(path: Path) -> Workflow:
    """Load a ``*.workflow.yaml|yml|json`` file.

    Raises:
        DocumentError: Bad file name or any error of `load_document`.
    """
    if not path.name.endswith(WORKFLOW_SUFFIXES):
        raise DocumentError(path, None, "Dateiname muss auf .workflow.yaml enden")
    return load_document(path, Workflow)
