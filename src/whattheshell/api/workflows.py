# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workflow endpoints on top of the workflow index; writes go to the user folder only."""

import io
import re
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import ValidationError
from ruamel.yaml import YAML

from whattheshell.api.errors import validation_errors
from whattheshell.api.rest import fail
from whattheshell.api.runs import create_run_response
from whattheshell.models.common import StrictModel
from whattheshell.models.workflow import Workflow
from whattheshell.modules.loader import DocumentError, load_workflow_file
from whattheshell.modules.store import user_dir, write_user_file
from whattheshell.workflows import WorkflowEntry, WorkflowIndex

router = APIRouter(prefix="/api/workflows")
SUFFIX = ".workflow.yaml"
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class DocumentBody(StrictModel):
    """Request body carrying a workflow document."""

    document: dict[str, Any]


def _check_id(workflow_id: str) -> str:
    if not _ID.fullmatch(workflow_id):
        raise fail(
            400,
            "workflow_id",
            f"Ungültige Workflow-id '{workflow_id}'. Erlaubt: Kleinbuchstaben, Ziffern, _ und -.",
        )
    return workflow_id


def _index(request: Request) -> WorkflowIndex:
    index: WorkflowIndex = request.app.state.workflows
    return index


def _refuse_if_shadowed(request: Request, workflow_id: str) -> None:
    """A project file wins over the user folder: writing there would change nothing visible."""
    entry = _index(request).get(workflow_id)
    if entry is not None and entry.source == "project":
        raise fail(
            409,
            "shadowed",
            f"'{workflow_id}' wird von der Projektdatei {entry.path} (Quelle project) überdeckt. "
            "Dort von Hand ändern oder entfernen.",
        )


def _find(request: Request, workflow_id: str) -> WorkflowEntry:
    """Winning entry of an existing workflow."""
    entry = _index(request).get(_check_id(workflow_id))
    if entry is None:
        raise fail(404, "workflow_not_found", f"Workflow '{workflow_id}' gibt es nicht.")
    return entry


def _validate(document: dict[str, Any]) -> Workflow:
    try:
        return Workflow.model_validate(document)
    except ValidationError as err:
        raise fail(
            422, "validation", "Workflow ist ungültig.", errors=validation_errors(err)
        ) from err


@router.get("")
def list_workflows(request: Request) -> list[dict[str, Any]]:
    """Index entries; the highest-priority file of an id wins, `shadows` names the others."""
    return [
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "source": e.source,
            "path": str(e.path),
            "variables": {k: v.model_dump(mode="json") for k, v in e.variables.items()},
            "steps": e.steps,
            "error": e.error,
            "shadows": e.shadows,
            "writable": e.source != "project",
        }
        for e in sorted(_index(request).all(), key=lambda e: e.id)
    ]


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, request: Request) -> dict[str, Any]:
    """Document and raw text of one workflow."""
    path = _find(request, workflow_id).path
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
def put_workflow(workflow_id: str, body: DocumentBody, request: Request) -> dict[str, str]:
    """Validate and write the user file; other sources stay untouched (copy semantics)."""
    _check_id(workflow_id)
    _refuse_if_shadowed(request, workflow_id)
    workflow = _validate(body.document)
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.sort_base_mapping_type_on_output = False  # type: ignore[assignment]  # keep field order
    buffer = io.StringIO()
    yaml.dump(workflow.model_dump(mode="json", exclude_defaults=True), buffer)
    try:
        target = write_user_file("workflow", f"{workflow_id}{SUFFIX}", buffer.getvalue())
    except OSError as err:
        raise fail(
            500,
            "write",
            f"Workflow nicht schreibbar: {err}. Prüfe Rechte auf {user_dir('workflow')}.",
        ) from err
    _index(request).reload(target)
    return {"id": workflow_id, "path": str(target)}


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str, request: Request) -> Response:
    """Delete the user file; bundled and project files cannot be deleted here."""
    _check_id(workflow_id)
    _refuse_if_shadowed(request, workflow_id)
    target = user_dir("workflow") / f"{workflow_id}{SUFFIX}"
    if not target.is_file():
        entry = _index(request).get(workflow_id)
        if entry is not None:
            raise fail(
                403,
                "not_deletable",
                f"'{workflow_id}' liegt in der Quelle '{entry.source}' ({entry.path}) und ist "
                "hier nicht löschbar. Projektdateien gehören zum Projekt: dort von Hand entfernen.",
            )
        raise fail(404, "workflow_not_found", f"Workflow '{workflow_id}' gibt es nicht.")
    try:
        target.unlink()
    except OSError as err:
        raise fail(500, "write", f"Workflow nicht löschbar: {err}.") from err
    _index(request).reload(target)
    return Response(status_code=204)


class RunWorkflowBody(StrictModel):
    """Request body of `POST /api/workflows/{id}/run`."""

    variables: dict[str, str] = {}
    cwd: str | None = None
    dry_run: bool = False


@router.post("/{workflow_id}/run")
def run_workflow(workflow_id: str, body: RunWorkflowBody, request: Request) -> Response:
    """Shortcut for `POST /api/runs` with the indexed document; same answer."""
    path = _find(request, workflow_id).path
    try:
        document = load_workflow_file(path).model_dump(mode="json")
    except DocumentError as err:
        raise fail(422, "workflow", str(err)) from err
    return create_run_response(request.app, document, body.variables, body.cwd, body.dry_run)


@router.post("/validate")
def validate_workflow(body: DocumentBody) -> dict[str, Any]:
    """Check a document without saving it."""
    try:
        Workflow.model_validate(body.document)
    except ValidationError as err:
        return {"ok": False, "errors": validation_errors(err)}
    return {"ok": True, "errors": []}
