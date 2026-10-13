# SPDX-License-Identifier: AGPL-3.0-or-later
"""REST endpoints of docs/API.md except runs and workflows."""

import dataclasses
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field, ValidationError

from whattheshell import APP_NAME, __version__, paths
from whattheshell.catalog import INTERACTIVE, Catalog, ToolNotFound
from whattheshell.engine.argv import ArgvError, build_argv, display
from whattheshell.models.catalog import ToolInfo
from whattheshell.models.common import StrictModel, ToolName
from whattheshell.modules.i18n import TEXT_FIELDS, translate_command
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.safety import classify_command
from whattheshell.sandbox import SandboxStatus, run_sandboxed, self_test
from whattheshell.sandbox.examples import write_fixtures

router = APIRouter(prefix="/api")


def fail(status: int, error: str, message: str, **extra: Any) -> HTTPException:
    """Build an HTTPException whose body is ``{"error", "message", ...}`` (see app handlers)."""
    return HTTPException(status, {"error": error, "message": message, **extra})


# Subcommand words never start with a dash or contain shell characters (option injection).
SUB_WORD = r"^[A-Za-z][A-Za-z0-9_-]*$"
SubWord = Annotated[str, Field(pattern=SUB_WORD)]
Lang = Annotated[str, Query(pattern=r"^[a-z]{2,3}$")]  # "de" = original texts of the modules
PREVIEW_SLOTS = threading.Semaphore(2)
PREVIEW_WAIT = 15.0


class CommandBody(StrictModel):
    """Tool, subcommand words and field values of a command."""

    tool: ToolName
    command: list[SubWord] = []
    args: dict[str, Any] = {}
    extra_args: list[str] = []


class PreviewBody(CommandBody):
    """Command plus optional module example (index) and stdin text."""

    example: int | None = None
    stdin: str | None = None


def _sandbox(request: Request, *, recheck: bool = False) -> SandboxStatus:
    # ponytail: no lock, two parallel first calls both run the self test; harmless
    if recheck or getattr(request.app.state, "sandbox", None) is None:
        request.app.state.sandbox = self_test()
        # help of tools is fetched in the sandbox once it is known to work
        request.app.state.catalog.sandbox = request.app.state.sandbox
        request.app.state.raw_catalog.sandbox = request.app.state.sandbox
    status: SandboxStatus = request.app.state.sandbox
    return status


def _get_info(
    request: Request,
    tool: str,
    sub: list[str],
    *,
    deep: int = 0,
    refresh: bool = False,
    catalog: Catalog | None = None,
) -> ToolInfo:
    catalog = catalog or request.app.state.catalog
    try:
        return catalog.get(tool, sub, depth=deep, refresh=refresh)
    except ToolNotFound as err:
        raise fail(404, "tool_not_found", str(err)) from err
    except (OSError, ValidationError) as err:
        raise fail(
            500,
            "tool_unreadable",
            f"Tool '{tool}' konnte nicht gelesen werden: {err}. Prüfe Rechte oder nutze refresh=1.",
        ) from err


def _module_errors(registry: ModuleRegistry) -> list[dict[str, Any]]:
    return [{"path": str(e.path), "line": e.line, "message": e.message} for e in registry.errors]


@router.get("/status")
def status(request: Request) -> dict[str, Any]:
    """App, version, sandbox state and module load errors."""
    registry: ModuleRegistry = request.app.state.registry
    return {
        "app": APP_NAME,
        "version": __version__,
        "sandbox": dataclasses.asdict(_sandbox(request)),
        "module_errors": _module_errors(registry),
        "config_dir": str(paths.config_dir()),
        "workflows_dir": str(paths.config_dir() / "workflows"),
        "modules_watch": request.app.state.modules_watch,
        "workflows_watch": request.app.state.workflows_watch,
    }


@router.post("/sandbox/selftest")
def sandbox_selftest(request: Request) -> dict[str, Any]:
    """Re-run the sandbox self test and replace the cached result."""
    return dataclasses.asdict(_sandbox(request, recheck=True))


@router.get("/tools")
def list_tools(request: Request, search: str = "", lang: Lang = "de") -> list[dict[str, Any]]:
    """Executables on PATH, enriched from loaded modules only (no help is fetched)."""
    catalog: Catalog = request.app.state.catalog
    registry: ModuleRegistry = request.app.state.registry
    needle = search.lower()
    result: list[dict[str, Any]] = []
    for tool in catalog.tools():
        loaded = registry.for_tool(tool.name)
        module = loaded[-1].module if loaded else None
        if module and lang != "de" and (text := module.i18n.get(lang)):
            module = module.model_copy(
                update=text.model_dump(exclude_none=True, include=TEXT_FIELDS)
            )
        display_name = module.display_name if module else None
        if (
            needle
            and needle not in tool.name.lower()
            and needle not in (display_name or "").lower()
        ):
            continue
        interactive = tool.name in INTERACTIVE  # same rule as Catalog._build, no process start
        if module and module.interactive is not None:
            interactive = module.interactive
        entry: dict[str, Any] = {"name": tool.name, "path": tool.path, "interactive": interactive}
        if module:
            extra = {
                "display_name": display_name,
                "category": module.category,
                "summary": module.summary,
                "safety": module.safety,
            }
            entry |= {key: value for key, value in extra.items() if value is not None}
        result.append(entry)
    return result


@router.get("/tools/{name}")
def tool_detail(
    request: Request,
    name: ToolName,
    sub: str = "",
    deep: Annotated[int, Query(ge=0, le=1)] = 0,
    refresh: Annotated[int, Query(ge=0, le=1)] = 0,
    lang: Lang = "de",
) -> ToolInfo:
    """Catalog entry of a tool or subcommand; unknown subcommands are never probed."""
    _sandbox(request)  # both catalogs must know the sandbox before any help is fetched
    words = sub.split("/") if sub else []
    if bad := next((w for w in words if not re.fullmatch(SUB_WORD, w)), None):
        raise fail(
            422,
            "sub",
            f"Ungültiger Subbefehl {bad!r}. Erlaubt: Buchstaben, Ziffern, _ und -, "
            "beginnend mit einem Buchstaben.",
        )
    info = _get_info(request, name, words, deep=deep, refresh=bool(refresh))
    if lang == "de":
        return info
    return info.model_copy(update={"command": translate_command(info.command, lang)})


@router.get("/modules")
def modules(request: Request) -> dict[str, Any]:
    """Search paths and loaded modules, like ``wts modules``."""
    registry: ModuleRegistry = request.app.state.registry
    loaded = registry.all()
    return {
        "search_paths": [
            {
                "dir": str(directory),
                "count": sum(1 for m in loaded if m.path.parent == directory),
                "exists": directory.is_dir(),
            }
            for directory in registry.dirs
        ],
        "modules": [
            {"priority": m.priority, "tool": m.module.tool, "path": str(m.path)}
            for m in sorted(loaded, key=lambda m: (m.priority, m.module.tool))
        ],
        "errors": [
            {"path": str(e.path), "line": e.line, "message": e.message} for e in registry.errors
        ],
    }


def _argv(request: Request, body: CommandBody) -> tuple[ToolInfo, list[str]]:
    info = _get_info(request, body.tool, body.command)
    try:
        return info, build_argv(info.command, body.args, body.extra_args, tool_path=info.path)
    except ArgvError as err:
        raise fail(422, "argv", str(err)) from err


@router.post("/command")
def command(request: Request, body: CommandBody) -> dict[str, Any]:
    """Build argv, display string and safety verdict; nothing is executed."""
    info, argv = _argv(request, body)
    verdict = classify_command(info.command, body.args, body.extra_args)
    return {
        "argv": argv,
        "display": display(argv),
        "safety": verdict.safety,
        "reasons": list(verdict.reasons),
    }


@router.post("/preview")
def preview(request: Request, body: PreviewBody) -> dict[str, Any]:
    """Run the command in the bwrap sandbox (never unsandboxed) and return its output."""
    status = _sandbox(request)
    if not status.available:
        raise fail(
            409,
            "sandbox",
            f"Sandbox nicht verfügbar: {status.reason}",
            reason=status.reason,
            install_hint=status.install_hint,
        )
    info, argv = _argv(request, body)
    with tempfile.TemporaryDirectory(prefix="wts-preview-") as tmp:
        workdir = Path(tmp)
        if body.example is not None:
            examples = info.command.examples
            if not 0 <= body.example < len(examples):
                raise fail(
                    422,
                    "example",
                    f"Beispiel {body.example} gibt es nicht ({len(examples)} vorhanden).",
                )
            if problems := write_fixtures(examples[body.example], workdir):
                raise fail(422, "example", "; ".join(problems))
        if not PREVIEW_SLOTS.acquire(timeout=PREVIEW_WAIT):
            raise fail(
                429, "busy", "Zu viele Vorschauen gleichzeitig. Warte kurz und versuche es erneut."
            )
        try:
            start = time.monotonic()
            done = run_sandboxed(
                argv,
                workdir,
                stdin=None if body.stdin is None else body.stdin.encode(),
                timeout=10,
            )
            duration = time.monotonic() - start
        finally:
            PREVIEW_SLOTS.release()
    if done is None:
        raise fail(500, "sandbox", "Sandbox konnte nicht starten. Prüfe /api/sandbox/selftest.")
    return {
        "command": display(argv),
        "exit_code": done.exit_code,
        "stdout": done.stdout.decode(errors="replace"),
        "stderr": done.stderr.decode(errors="replace"),
        "duration": duration,
        "truncated": done.truncated,
        "timed_out": done.timed_out,
    }
