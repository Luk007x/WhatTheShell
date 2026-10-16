# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workflow endpoints on top of the workflow index; writes go to the user folder only."""

import io
import re
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from ruamel.yaml import YAML

from whattheshell import integrity
from whattheshell.api.errors import validation_errors
from whattheshell.api.rest import fail
from whattheshell.api.runs import create_run_response
from whattheshell.i18n import _
from whattheshell.models.common import StrictModel
from whattheshell.models.workflow import Workflow
from whattheshell.modules.loader import DocumentError, load_workflow_file
from whattheshell.modules.store import (
    IMPORT_NAME,
    MAX_IMPORT_BYTES,
    user_dir,
    validate_workflow_text,
    write_user_file,
)
from whattheshell.workflows import WorkflowEntry, WorkflowIndex, integrity_of, shadow_message

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
            _(
                "Ungültige Workflow-id '{workflow_id}'. "
                "Erlaubt: Kleinbuchstaben, Ziffern, _ und -.",
                workflow_id=workflow_id,
            ),
        )
    return workflow_id


def _index(request: Request) -> WorkflowIndex:
    index: WorkflowIndex = request.app.state.workflows
    return index


def _refuse_if_shadowed(request: Request, workflow_id: str) -> None:
    message = shadow_message(_index(request), workflow_id)
    if message is not None:
        raise fail(409, "shadowed", message)


def _find(request: Request, workflow_id: str) -> WorkflowEntry:
    """Winning entry of an existing workflow."""
    entry = _index(request).get(_check_id(workflow_id))
    if entry is None:
        raise fail(
            404,
            "workflow_not_found",
            _("Workflow '{workflow_id}' gibt es nicht.", workflow_id=workflow_id),
        )
    return entry


def _validate(document: dict[str, Any]) -> Workflow:
    try:
        return Workflow.model_validate(document)
    except ValidationError as err:
        raise fail(
            422, "validation", _("Workflow ist ungültig."), errors=validation_errors(err)
        ) from err


def _item(e: WorkflowEntry) -> dict[str, Any]:
    return {
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
        "integrity": integrity_of(e),
    }


@router.get("")
def list_workflows(request: Request) -> list[dict[str, Any]]:
    """Index entries; the highest-priority file of an id wins, `shadows` names the others."""
    return [_item(e) for e in sorted(_index(request).all(), key=lambda e: e.id)]


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, request: Request) -> dict[str, Any]:
    """Document and raw text of one workflow."""
    entry = _find(request, workflow_id)
    path = entry.path
    try:
        workflow = load_workflow_file(path)
        raw = path.read_text(encoding="utf-8")
    except (DocumentError, OSError) as err:
        raise fail(422, "workflow", str(err)) from err
    return {
        "id": workflow_id,
        "path": str(path),
        "source": entry.source,
        "integrity": integrity_of(entry),
        "error": entry.error,
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
            _(
                "Workflow nicht schreibbar: {err}. Prüfe Rechte auf {folder}.",
                err=err,
                folder=user_dir("workflow"),
            ),
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
                _(
                    "'{workflow_id}' liegt in der Quelle '{source}' ({path}) und ist "
                    "hier nicht löschbar. Projektdateien gehören zum Projekt: "
                    "dort von Hand entfernen.",
                    workflow_id=workflow_id,
                    source=entry.source,
                    path=entry.path,
                ),
            )
        raise fail(
            404,
            "workflow_not_found",
            _("Workflow '{workflow_id}' gibt es nicht.", workflow_id=workflow_id),
        )
    try:
        target.unlink()
    except OSError as err:
        raise fail(500, "write", _("Workflow nicht löschbar: {err}.", err=err)) from err
    _index(request).reload(target)
    return Response(status_code=204)


class RunWorkflowBody(StrictModel):
    """Request body of `POST /api/workflows/{id}/run`."""

    variables: dict[str, str] = {}
    cwd: str | None = None
    dry_run: bool = False
    transcript: bool = False  # as RunBody: save terminal output (SECURITY.md 7.4)


@router.post("/{workflow_id}/run")
def run_workflow(workflow_id: str, body: RunWorkflowBody, request: Request) -> Response:
    """Shortcut for `POST /api/runs` with the indexed document; same answer."""
    entry = _find(request, workflow_id)
    try:
        document = load_workflow_file(entry.path).model_dump(mode="json")
    except DocumentError as err:
        raise fail(422, "workflow", str(err)) from err
    state = integrity_of(entry)
    if state in ("modified", "unstamped") and not body.dry_run:  # a plan runs nothing
        return JSONResponse(
            {"error": "integrity", "status": state, "message": _(integrity.REFUSAL)}, 409
        )
    return create_run_response(
        request.app, document, body.variables, body.cwd, body.dry_run, body.transcript
    )


class ImportBody(StrictModel):
    """Request body of `POST /api/workflows/import`."""

    filename: str
    content: str
    overwrite: bool = False


@router.post("/import", status_code=201)
def import_workflow(body: ImportBody, request: Request) -> dict[str, Any]:
    """Validate YAML text like a file and write it into the user folder (stamped)."""
    if not IMPORT_NAME.fullmatch(body.filename):
        raise fail(
            400,
            "filename",
            _(
                "Ungültiger Dateiname '{filename}'. Erwartet: id{suffix} "
                "(Kleinbuchstaben, Ziffern, _ und -, ohne Pfad).",
                filename=body.filename,
                suffix=SUFFIX,
            ),
        )
    try:
        size = len(body.content.encode("utf-8", "surrogatepass"))
        body.content.encode("utf-8")  # lone surrogates cannot be written
    except UnicodeEncodeError as err:
        raise fail(
            422, "encoding", _("Inhalt ist kein gültiges UTF-8: {reason}.", reason=err.reason)
        ) from err
    if size > MAX_IMPORT_BYTES:
        raise fail(413, "too_large", _("Datei größer als {limit} Byte.", limit=MAX_IMPORT_BYTES))
    workflow_id = body.filename.removesuffix(SUFFIX)
    _refuse_if_shadowed(request, workflow_id)
    workflow, lines = validate_workflow_text(body.content)
    if workflow is None:
        raise fail(
            422,
            "validation",
            _("Workflow ist ungültig."),
            errors=[{"path": "", "message": line} for line in lines],
        )
    if (user_dir("workflow") / body.filename).exists() and not body.overwrite:
        raise fail(
            409,
            "exists",
            _(
                "'{filename}' gibt es im Nutzerordner schon. Mit overwrite=true ersetzen.",
                filename=body.filename,
            ),
        )
    try:
        target = write_user_file("workflow", body.filename, body.content)
    except OSError as err:
        raise fail(
            500,
            "write",
            _(
                "Workflow nicht schreibbar: {err}. Prüfe Rechte auf {folder}.",
                err=err,
                folder=user_dir("workflow"),
            ),
        ) from err
    _index(request).reload(target)
    return _item(_find(request, workflow_id))


@router.post("/{workflow_id}/accept")
def accept_workflow(workflow_id: str, request: Request) -> dict[str, Any]:
    """Re-validate the current file and stamp it: the user vouches for the outside edit."""
    entry = _find(request, workflow_id)
    if entry.source == "bundled":
        return _item(entry)  # read-only package data, always ok
    try:
        load_workflow_file(entry.path)
        integrity.stamp(entry.path)
    except DocumentError as err:
        raise fail(422, "workflow", str(err)) from err
    except OSError as err:
        raise fail(500, "write", _("Stempel nicht schreibbar: {err}.", err=err)) from err
    _index(request).reload(entry.path)
    return _item(_find(request, workflow_id))


@router.post("/validate")
def validate_workflow(body: DocumentBody) -> dict[str, Any]:
    """Check a document without saving it."""
    try:
        Workflow.model_validate(body.document)
    except ValidationError as err:
        return {"ok": False, "errors": validation_errors(err)}
    return {"ok": True, "errors": []}
