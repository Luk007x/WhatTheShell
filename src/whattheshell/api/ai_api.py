# SPDX-License-Identifier: AGPL-3.0-or-later
"""``/api/ai/*``: two-phase AI tasks (data preview, then send) and approval of results.

Every endpoint passes the gate first. Nothing a model returns is saved or run here except by
``POST /api/ai/apply``, which re-validates and writes into the user's folders only.
"""

import re
import threading
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from whattheshell import paths
from whattheshell.ai import AiDisabled, require_enabled
from whattheshell.ai import tasks as ai_tasks
from whattheshell.ai.approve import Approval, apply, propose
from whattheshell.ai.docs import read_doc
from whattheshell.ai.protocol import Prompt, make_provider
from whattheshell.api.modules_api import _user_path
from whattheshell.api.rest import _get_info, _sandbox, fail
from whattheshell.engine import mask_text
from whattheshell.models.common import StrictModel, ToolName
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.modules.scaffold import scaffold_module
from whattheshell.modules.store import (
    registry_module_text,
    validate_module_text,
    validate_workflow_text,
)
from whattheshell.settings import Settings

AI_SLOTS = threading.Semaphore(2)
AI_WAIT = 15.0
FILE_STEM = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]


def _gate(request: Request) -> None:
    try:
        require_enabled(request.app.state.settings)
    except AiDisabled as err:
        raise fail(403, "ai_disabled", str(err)) from err


router = APIRouter(prefix="/api/ai", dependencies=[Depends(_gate)])


class _Task(StrictModel):
    send: bool = False


class ToolTask(_Task):
    """`improve-module` and `examples`."""

    tool: ToolName


class DraftTask(_Task):
    """`draft-workflow`: free text, optional file name stem."""

    description: str = Field(min_length=1)
    name: FILE_STEM | None = None


class DiagnoseTask(_Task):
    """`diagnose`: a step as in ``RunResult.results``."""

    step: dict[str, Any]
    include_output: bool = False


class ApplyBody(StrictModel):
    """An accepted proposal."""

    kind: Literal["module", "workflow"]
    raw: str
    target_name: str


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else None
    except (OSError, UnicodeDecodeError) as err:
        raise fail(500, "read", f"{path} nicht lesbar: {err}. Prüfe Rechte.") from err


def _provider_call(settings: Settings, prompt: Prompt, secrets: list[str]) -> str:
    """Run the provider; at most two at once (429 after `AI_WAIT`), errors become 502."""
    if not AI_SLOTS.acquire(timeout=AI_WAIT):
        raise fail(429, "busy", "Zwei KI-Anfragen laufen bereits. Später erneut versuchen.")
    try:
        return make_provider(settings).complete(prompt)
    except (RuntimeError, OSError, ImportError) as err:
        raise fail(
            502,
            "ai_provider",
            f"Anbieter fehlgeschlagen: {ai_tasks.sanitize(str(err), secrets)}. "
            "Prüfe die Einstellungen (Anbieter, Schlüssel).",
        ) from err
    finally:
        AI_SLOTS.release()


def _run(
    request: Request,
    prompt: Prompt,
    send: bool,
    kind: Literal["module", "workflow", "text"],
    target: str | None = None,
    current: str | None = None,
    tool: str | None = None,
) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    secrets = ai_tasks.known_keys(settings.ai.api.key_env)
    prompt = Prompt(
        mask_text(prompt.system, secrets),
        mask_text(prompt.user, secrets),
        prompt.max_tokens,
    )
    if not send:
        return {
            "prompt": {"system": prompt.system, "user": prompt.user},
            "chars": len(prompt.system) + len(prompt.user),
        }
    answer = _provider_call(settings, prompt, secrets)
    if kind == "text":
        return {
            "kind": kind,
            "raw": ai_tasks.sanitize(answer, secrets),
            "errors": [],
            "diff": "",
            "target": None,
            "valid": True,
        }
    raw = ai_tasks.extract_yaml(answer)
    errors = _check(kind, raw, tool, target)
    return {
        "kind": kind,
        "raw": raw,
        "errors": errors,
        "diff": propose(kind, Path(target) if target else None, current, raw, errors).diff,
        "target": target,
        "valid": not errors,
    }


def _check(kind: str, raw: str, tool: str | None, target: str | None) -> list[str]:
    """Task validators plus: the module belongs to `tool` / its file name."""
    if kind == "workflow":
        return validate_workflow_text(raw)[1]
    module, errors = validate_module_text(raw)
    stem = (target or "").partition(".module.")[0]
    if module is not None and module.tool != (tool or stem):
        errors.append(f"tool ist '{module.tool}', erwartet '{tool or stem}'")
    return errors


def _module_task(request: Request, body: ToolTask, *, examples: bool) -> dict[str, Any]:
    _sandbox(request)
    info = _get_info(request, body.tool, [])
    current = _read(_user_path(body.tool))
    if current is None:  # no user file: the effective (e.g. bundled) module is the baseline
        try:
            current = registry_module_text(body.tool, request.app.state.registry)
        except OSError as err:
            raise fail(500, "read", f"Modul nicht lesbar: {err}. Prüfe Rechte.") from err
    inspect_json = info.model_dump_json(indent=2)
    if examples:
        base = current or scaffold_module(
            _get_info(request, body.tool, [], catalog=request.app.state.raw_catalog)
        )
        prompt = ai_tasks.generate_examples(body.tool, base, inspect_json)
    else:
        prompt = ai_tasks.improve_module(
            body.tool,
            current_raw=current,
            inspect_json=inspect_json,
            authoring_doc=read_doc("MODULE_AUTHORING.md"),
        )
    target = f"{body.tool}.module.yaml"
    return _run(request, prompt, body.send, "module", target, current, body.tool)


@router.post("/improve-module")
def improve_module(request: Request, body: ToolTask) -> dict[str, Any]:
    """Write or improve the module of a tool."""
    return _module_task(request, body, examples=False)


@router.post("/examples")
def examples(request: Request, body: ToolTask) -> dict[str, Any]:
    """Add examples and fixtures to the module of a tool."""
    return _module_task(request, body, examples=True)


@router.post("/draft-workflow")
def draft_workflow(request: Request, body: DraftTask) -> dict[str, Any]:
    """Draft a workflow from a description; the file name stem comes from `name` or the answer."""
    registry: ModuleRegistry = request.app.state.registry
    hint = "\n".join(
        f"{m.module.tool}: " + ", ".join(f.id for f in (*m.module.inputs, *m.module.options))
        for m in registry.all()
    )
    prompt = ai_tasks.draft_workflow(
        body.description, hint, read_doc("FORMATS.md", "## 4.", "## 5.")
    )
    result = _run(
        request, prompt, body.send, "workflow", body.name and f"{body.name}.workflow.yaml"
    )
    workflow = validate_workflow_text(result["raw"])[0] if body.send else None
    if workflow is not None and result["target"] is None:
        stem = re.sub(r"[^a-z0-9]+", "-", workflow.name.lower()).strip("-")
        result["target"] = f"{stem or 'workflow'}.workflow.yaml"
    return result


@router.post("/diagnose")
def diagnose(request: Request, body: DiagnoseTask) -> dict[str, Any]:
    """Explain a failed step; outputs are only sent with `include_output` or `send_outputs`."""
    include = body.include_output or request.app.state.settings.ai.send_outputs
    step = (
        body.step
        if include
        else {k: v for k, v in body.step.items() if k not in ("stdout", "stderr")}
    )
    return _run(request, ai_tasks.diagnose(step, include), body.send, "text")


@router.post("/apply")
def apply_proposal(request: Request, body: ApplyBody) -> dict[str, str]:
    """Validate again and write a proposal into the user's folder (module: registry reloads)."""
    errors = _check(body.kind, body.raw, None, body.target_name)
    approval = Approval(body.kind, Path(body.target_name), None, body.raw, "", errors)
    try:
        path = apply(approval)
    except ValueError as err:
        raise fail(
            422, "validation", str(err), errors=[{"path": "", "message": e} for e in errors]
        ) from err
    except OSError as err:
        raise fail(
            500, "write", f"Nicht schreibbar: {err}. Prüfe Rechte auf {paths.config_dir()}."
        ) from err
    if body.kind == "module":
        request.app.state.registry.reload(path)
    return {"path": str(path)}
