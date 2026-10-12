# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module files (user overrides of bundled ones) and workflow templates of modules."""

import shutil
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Request, Response
from pydantic import Field

from whattheshell import bundled, paths
from whattheshell.api.rest import SUB_WORD, _get_info, _sandbox, fail
from whattheshell.catalog import Catalog
from whattheshell.models.common import StrictModel, ToolName
from whattheshell.modules.loader import DocumentError, load_module_file, load_workflow_file
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.modules.scaffold import scaffold_module
from whattheshell.modules.store import load_module_text, write_user_file

router = APIRouter(prefix="/api/modules")
templates_router = APIRouter(prefix="/api/templates")
SUFFIX = ".module.yaml"
WORKFLOW_SUFFIX = ".workflow.yaml"


class RawBody(StrictModel):
    """Module file text; the raw text is the truth, the GUI form only generates it."""

    raw: str


class ScaffoldBody(StrictModel):
    """Tool and subcommand words to build a module skeleton for."""

    tool: ToolName
    command: list[Annotated[str, Field(pattern=SUB_WORD)]] = []


def _user_path(tool: str) -> Path:
    return paths.config_dir() / "modules" / f"{tool}{SUFFIX}"


def _bundled_path(tool: str) -> Path:
    return bundled.MODULES_DIR / f"{tool}{SUFFIX}"


def _error_list(err: DocumentError) -> list[dict[str, Any]]:
    return [{"path": err.path.name, "line": err.line, "message": err.message}]


@router.get("/{tool}")
def get_module(tool: ToolName) -> dict[str, Any]:
    """Raw text and parsed document of a module; the user file wins over the bundled one."""
    candidates = (("user", _user_path(tool)), ("bundled", _bundled_path(tool)))
    source, path = next(
        ((s, p) for s, p in candidates if p.is_symlink() or p.is_file()), (None, None)
    )
    if path is None:
        raise fail(
            404,
            "module_not_found",
            f"Für '{tool}' gibt es kein Modul. Mit POST /api/modules/scaffold entsteht ein Gerüst.",
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        raise fail(500, "read", f"Modul nicht lesbar: {err}. Prüfe Rechte auf {path}.") from err
    try:  # a broken user file is still returned raw, so it can be fixed
        document = load_module_file(path).model_dump(mode="json", exclude_defaults=True)
        errors: list[dict[str, Any]] = []
    except DocumentError as err:
        document, errors = None, _error_list(err)
    return {
        "tool": tool,
        "source": source,
        "path": str(path),
        "raw": raw,
        "document": document,
        "errors": errors,
        "scaffold_available": shutil.which(tool) is not None,
    }


@router.put("/{tool}")
def put_module(request: Request, tool: ToolName, body: RawBody) -> dict[str, str]:
    """Validate the text and write the user file (a bundled module stays untouched)."""
    try:
        module = load_module_text(body.raw)
    except DocumentError as err:
        raise fail(422, "validation", "Modul ist ungültig.", errors=_error_list(err)) from err
    if module.tool != tool:
        raise fail(
            422,
            "tool_mismatch",
            f"Das Modul beschreibt '{module.tool}', nicht '{tool}'. Passe 'tool:' an.",
        )
    try:
        target = write_user_file("module", f"{tool}{SUFFIX}", body.raw)
    except OSError as err:
        raise fail(
            500,
            "write",
            f"Modul nicht schreibbar: {err}. Prüfe Rechte auf {_user_path(tool).parent}.",
        ) from err
    registry: ModuleRegistry = request.app.state.registry
    registry.reload(target)
    return {"tool": tool, "path": str(target)}


@router.delete("/{tool}", status_code=204)
def delete_module(request: Request, tool: ToolName) -> Response:
    """Delete the user file; a bundled module without one cannot be deleted."""
    target = _user_path(tool)
    if not (target.is_symlink() or target.is_file()):
        if _bundled_path(tool).is_file():
            raise fail(403, "bundled", f"'{tool}' ist mitgeliefert und nicht löschbar.")
        raise fail(404, "module_not_found", f"Für '{tool}' gibt es kein Nutzermodul.")
    try:
        target.unlink()
    except OSError as err:
        raise fail(500, "write", f"Modul nicht löschbar: {err}.") from err
    registry: ModuleRegistry = request.app.state.registry
    registry.reload(target)
    return Response(status_code=204)


@router.post("/scaffold")
def scaffold(request: Request, body: ScaffoldBody) -> dict[str, str]:
    """Module skeleton from the raw catalog entry (no module overrides applied)."""
    _sandbox(request)
    raw_catalog: Catalog = request.app.state.raw_catalog
    info = _get_info(request, body.tool, body.command, catalog=raw_catalog)
    return {"raw": scaffold_module(info)}


@templates_router.get("/{tool}")
def templates(request: Request, tool: ToolName) -> list[dict[str, Any]]:
    """Workflow templates of all modules of a tool, paths relative to the module file."""
    registry: ModuleRegistry = request.app.state.registry
    result: list[dict[str, Any]] = []
    for loaded in registry.for_tool(tool):
        for ref in loaded.module.templates:
            path = loaded.path.parent / ref.workflow
            entry: dict[str, Any] = {"title": ref.title}
            try:
                document = load_workflow_file(path).model_dump(mode="json")
                workflow_id = path.name.removesuffix(WORKFLOW_SUFFIX)
                entry["workflow"] = {"id": workflow_id, "document": document}
            except DocumentError as err:
                entry["workflow"] = {"id": None, "document": None}
                entry["error"] = err.message
            result.append(entry)
    return result
