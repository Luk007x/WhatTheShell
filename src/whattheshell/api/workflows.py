# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workflow files: user files in ``config_dir()/workflows`` shadow bundled ones of the same id."""

import io
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response
from pydantic import ValidationError
from ruamel.yaml import YAML

from whattheshell import bundled, paths
from whattheshell.api.errors import validation_errors
from whattheshell.api.rest import fail
from whattheshell.models.common import StrictModel
from whattheshell.models.workflow import Workflow
from whattheshell.modules.loader import DocumentError, load_workflow_file

router = APIRouter(prefix="/api/workflows")
SUFFIX = ".workflow.yaml"
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class DocumentBody(StrictModel):
    """Request body carrying a workflow document."""

    document: dict[str, Any]


def _user_dir() -> Path:
    return paths.config_dir() / "workflows"


def _check_id(workflow_id: str) -> str:
    if not _ID.fullmatch(workflow_id):
        raise fail(
            400,
            "workflow_id",
            f"Ungültige Workflow-id '{workflow_id}'. Erlaubt: Kleinbuchstaben, Ziffern, _ und -.",
        )
    return workflow_id


def _is_bundled(workflow_id: str) -> bool:
    return (bundled.WORKFLOWS_DIR / f"{workflow_id}{SUFFIX}").is_file()


def _find(workflow_id: str) -> Path:
    """Path of an existing workflow (user file wins over bundled)."""
    for directory in (_user_dir(), bundled.WORKFLOWS_DIR):
        candidate = directory / f"{_check_id(workflow_id)}{SUFFIX}"
        if candidate.is_file():
            return candidate
    raise fail(404, "workflow_not_found", f"Workflow '{workflow_id}' gibt es nicht.")


def _validate(document: dict[str, Any]) -> Workflow:
    try:
        return Workflow.model_validate(document)
    except ValidationError as err:
        raise fail(
            422, "validation", "Workflow ist ungültig.", errors=validation_errors(err)
        ) from err


@router.get("")
def list_workflows() -> list[dict[str, str]]:
    """Bundled and user workflows; a user file with the same id replaces the bundled entry."""
    found: dict[str, dict[str, str]] = {}
    for source, directory in (("bundled", bundled.WORKFLOWS_DIR), ("user", _user_dir())):
        for path in sorted(directory.glob(f"*{SUFFIX}")) if directory.is_dir() else []:
            workflow_id = path.name.removesuffix(SUFFIX)
            if not _ID.fullmatch(workflow_id):
                continue
            try:
                name = load_workflow_file(path).name
            except DocumentError:
                name = workflow_id  # broken file stays visible; GET reports the error
            found[workflow_id] = {
                "id": workflow_id, "name": name, "path": str(path), "source": source,
            }  # fmt: skip
    return list(found.values())


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str) -> dict[str, Any]:
    """Document and raw text of one workflow."""
    path = _find(workflow_id)
    try:
        workflow = load_workflow_file(path)
        raw = path.read_text(encoding="utf-8")
    except (DocumentError, OSError) as err:
        raise fail(422, "workflow", str(err)) from err
    return {
        "id": workflow_id,
        "path": str(path),
        "document": workflow.model_dump(mode="json"),
        "raw": raw,
    }


@router.put("/{workflow_id}")
def put_workflow(workflow_id: str, body: DocumentBody) -> dict[str, str]:
    """Validate and write the user file; a bundled workflow stays untouched (copy semantics)."""
    _check_id(workflow_id)
    workflow = _validate(body.document)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.sort_base_mapping_type_on_output = False  # type: ignore[assignment]  # keep field order
    buffer = io.StringIO()
    yaml.dump(workflow.model_dump(mode="json", exclude_defaults=True), buffer)
    target = _user_dir() / f"{workflow_id}{SUFFIX}"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # write beside the target and rename, so a crash never leaves a half-written workflow
        partial = target.with_name(target.name + ".tmp")
        partial.write_text(buffer.getvalue(), encoding="utf-8")
        partial.replace(target)
    except OSError as err:
        raise fail(
            500, "write", f"Workflow nicht schreibbar: {err}. Prüfe Rechte auf {target.parent}."
        ) from err
    return {"id": workflow_id, "path": str(target)}


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str) -> Response:
    """Delete the user file; bundled workflows without one cannot be deleted."""
    _check_id(workflow_id)
    target = _user_dir() / f"{workflow_id}{SUFFIX}"
    if not target.is_file():
        if _is_bundled(workflow_id):
            raise fail(403, "bundled", f"'{workflow_id}' ist mitgeliefert und nicht löschbar.")
        raise fail(404, "workflow_not_found", f"Workflow '{workflow_id}' gibt es nicht.")
    try:
        target.unlink()
    except OSError as err:
        raise fail(500, "write", f"Workflow nicht löschbar: {err}.") from err
    return Response(status_code=204)


@router.post("/validate")
def validate_workflow(body: DocumentBody) -> dict[str, Any]:
    """Check a document without saving it."""
    try:
        Workflow.model_validate(body.document)
    except ValidationError as err:
        return {"ok": False, "errors": validation_errors(err)}
    return {"ok": True, "errors": []}
