# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command line entry point."""

import argparse
import contextlib
import dataclasses
import getpass
import html
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import termios
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from whattheshell import APP_NAME, __version__, instance, paths
from whattheshell.ai import AiDisabled, require_enabled
from whattheshell.ai import tasks as ai_tasks
from whattheshell.ai.approve import apply, propose, target_path
from whattheshell.ai.check import CheckResult, check
from whattheshell.ai.protocol import Prompt, make_provider
from whattheshell.catalog import Catalog, ToolNotFound
from whattheshell.engine import (
    TERMINAL_ONLY_GUI,
    AskAnswer,
    AskRequest,
    ConfirmRequest,
    Controller,
    Event,
    Message,
    OutputChunk,
    Prepared,
    RunError,
    Runner,
    RunResult,
    StepFinished,
    StepSkipped,
    StepStarted,
    WorkflowFinished,
    mask_text,
    plan,
    plan_text,
    secret_values,
)
from whattheshell.models.catalog import CommandSpec, ToolInfo
from whattheshell.models.common import Safety, ValueType
from whattheshell.models.schema import export_schemas
from whattheshell.models.workflow import AskStep, TerminalStep, iter_steps
from whattheshell.modules.loader import (
    MODULE_SUFFIXES,
    WORKFLOW_SUFFIXES,
    DocumentError,
    load_module_file,
    load_workflow_file,
)
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.modules.scaffold import scaffold_module
from whattheshell.modules.store import (
    atomic_write,
    registry_module_text,
    user_dir,
    validate_module_text,
    validate_workflow_text,
)
from whattheshell.modules.watch import watch_modules
from whattheshell.sandbox import ExampleResult, run_example, self_test
from whattheshell.settings import Settings, load_settings, save_settings
from whattheshell.subproc import printable
from whattheshell.workflows import WorkflowIndex


def _registry() -> ModuleRegistry:
    registry = ModuleRegistry(paths.module_dirs(Path.cwd()))
    registry.scan()
    return registry


def _clip(text: str, width: int = 80) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _format_command(command: CommandSpec) -> list[str]:
    lines = [f"Usage: {command.usage}"] if command.usage else []
    if command.summary:
        lines += ["Summary", f"  {command.summary}"]
    if command.inputs:
        lines.append("Inputs:")
        lines += [
            _clip(f"  {i.id}  {i.type}  required={i.required}  multiple={i.multiple}")
            for i in command.inputs
        ]
    if command.options:
        lines.append("Options:")
        for opt in command.options:
            first = (opt.help or "").strip().splitlines()[0] if opt.help else ""
            text = f"{opt.label}: {first}" if opt.label else first
            lines.append(_clip(f"  {', '.join(opt.flags)}  {opt.type}  {opt.confidence}  {text}"))
    elif command.raw_help is not None:
        count = len(command.raw_help.splitlines())
        lines.append(
            f"Keine Optionen erkannt, Baustein „Freie Argumente“ mit Rohtext ({count} Zeilen)"
        )
    if command.subcommands:
        lines.append("Subcommands:")
        lines += [_clip(f"  {c.name[-1]}  {c.summary or ''}".rstrip()) for c in command.subcommands]
    return lines


def _format_info(info: ToolInfo) -> str:
    head = (
        f"{info.command.display_name or info.name} ({info.path}), "
        f"{info.version or 'Version unbekannt'}, "
        f"Quelle {info.source}, Konfidenz {info.command.confidence}, "
        f"interaktiv {'ja' if info.command.interactive else 'nein'}"
    )
    modules = [f"Module: {', '.join(info.module_files)}"] if info.module_files else []
    return "\n".join([head, *modules, *_format_command(info.command)])


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Arguments without program name; defaults to sys.argv[1:].

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(prog="wts", description=APP_NAME)
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    commands = parser.add_subparsers(dest="command", required=False)
    schema = commands.add_parser("schema", help="JSON-Schemas verwalten")
    schema_commands = schema.add_subparsers(dest="schema_command", required=True)
    export = schema_commands.add_parser("export", help="Schemas aus den Modellen erzeugen")
    export.add_argument("--out", type=Path, default=Path("schemas"), help="Zielordner")
    tools = commands.add_parser("tools", help="Programme auf PATH auflisten")
    tools.add_argument("--search", help="Nur Namen, die diesen Text enthalten")
    inspect = commands.add_parser("inspect", help="Hilfe eines Tools als Katalogeintrag zeigen")
    inspect.add_argument("tool")
    inspect.add_argument("sub", nargs="*", help="Subbefehle")
    inspect.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    inspect.add_argument("--refresh", action="store_true", help="Cache ignorieren")
    inspect.add_argument(
        "--no-sandbox", action="store_true", help="Hilfe-Abruf auf dem Host statt in der Sandbox"
    )
    inspect.add_argument("--deep", action="store_true", help="Subbefehle eine Ebene mitlesen")
    validate = commands.add_parser("validate", help="Modul- und Workflow-Dateien prüfen")
    validate.add_argument("files", nargs="+", type=Path)
    scaffold = commands.add_parser("scaffold", help="Modul-Gerüst aus der Hilfe eines Tools")
    scaffold.add_argument("tool")
    scaffold.add_argument("sub", nargs="*", help="Subbefehle")
    target = scaffold.add_mutually_exclusive_group()
    target.add_argument("--out", type=Path, help="Zieldatei statt stdout (Ordner werden angelegt)")
    target.add_argument(
        "--user", action="store_true", help="In den Modulordner des Benutzers schreiben"
    )
    scaffold.add_argument("--force", action="store_true", help="Zieldatei überschreiben")
    run = commands.add_parser("run", help="Workflow ausführen")
    run.add_argument("file", type=Path, help="Workflow-Datei oder id aus `wts workflows`")
    run.add_argument("--dry-run", action="store_true", help="Nur den Plan zeigen")
    run.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Alle Bestätigungen mit ja beantworten (Abfrage-Schritte beantwortet es nicht)",
    )
    run.add_argument(
        "--var", action="append", default=[], metavar="NAME=WERT", help="Variable setzen"
    )
    run.add_argument("--cwd", type=Path, help="Arbeitsverzeichnis (Standard: aktuelles)")
    run.add_argument("--json", action="store_true", help="Ergebnis als JSON statt Live-Ausgabe")
    commands.add_parser("sandbox", help="Sandbox (bwrap) prüfen")
    example = commands.add_parser("example", help="Beispiele eines Tools in der Sandbox ausführen")
    example.add_argument("tool")
    example.add_argument("number", nargs="?", type=int, help="Nur dieses Beispiel (1-basiert)")
    example.add_argument("--all", action="store_true", help="Alle Beispiele (Standard)")
    commands.add_parser("workflows", help="Workflow-Bibliothek auflisten")
    modules = commands.add_parser("modules", help="Geladene Module auflisten")
    modules.add_argument("--watch", action="store_true", help="Änderungen live neu laden")
    gui = commands.add_parser("gui", help="Oberfläche starten (nur 127.0.0.1, mit Sitzungstoken)")
    gui.add_argument(
        "action",
        nargs="?",
        choices=["start", "stop", "status"],
        help="start: im Hintergrund, stop: beenden, status: läuft sie? (Standard: Vordergrund)",
    )
    gui.add_argument("--port", type=int, default=0, help="Port (Standard: freier Port)")
    gui.add_argument("--no-browser", action="store_true", help="Browser nicht öffnen")
    gui.add_argument(
        "--install-desktop", action="store_true", help="Menüeintrag (.desktop) für `wts gui start`"
    )
    terminal = commands.add_parser("terminal", help="Gespeicherte Terminal-Ausgaben")
    transcripts = terminal.add_subparsers(dest="terminal_command", required=True).add_parser(
        "transcripts", help="Transkripte auflisten oder löschen"
    )
    transcripts.add_argument("--delete", metavar="NAME", help="Dieses Transkript löschen")
    ai = commands.add_parser("ai", help="Optionale KI-Funktionen (standardmäßig aus)")
    ai_commands = ai.add_subparsers(dest="ai_command", required=True)
    ai_commands.add_parser("enable", help="KI-Funktionen einschalten")
    ai_commands.add_parser("disable", help="KI-Funktionen ausschalten")
    ai_commands.add_parser("status", help="Einstellungen zeigen (ohne Schlüssel)")
    ai_check = ai_commands.add_parser("check", help="Konfigurierte KI-Quelle prüfen")
    ai_check.add_argument("--no-network", action="store_true", help="Keinen Endpunkt kontaktieren")
    ai_config = ai_commands.add_parser("config", help="Einstellung ändern")
    ai_config_set = ai_config.add_subparsers(dest="config_command", required=True).add_parser(
        "set", help="z. B. `provider agent`, `agent.kind codex`, `api.model NAME`"
    )
    ai_config_set.add_argument("path", help="Punktpfad unterhalb von ai")
    ai_config_set.add_argument("value", help="Wert (JSON oder Text)")
    improve = ai_commands.add_parser("improve-module", help="Modul verbessern oder neu schreiben")
    improve.add_argument("tool")
    improve.add_argument("--out", type=Path, help="Dateiname im Modulordner des Benutzers")
    examples = ai_commands.add_parser("examples", help="Beispiele und fixtures ergänzen")
    examples.add_argument("tool")
    draft = ai_commands.add_parser("draft-workflow", help="Workflow aus einer Beschreibung")
    draft.add_argument("description")
    draft.add_argument("--name", help="Dateiname (ohne Endung) im Workflow-Ordner")
    diagnose = ai_commands.add_parser("diagnose", help="Fehlgeschlagenen Schritt erklären")
    diagnose.add_argument("run_json", type=Path, help="Ausgabe von `wts run --json`")
    diagnose.add_argument("step_id")
    diagnose.add_argument(
        "--include-output", action="store_true", help="stdout/stderr mitsenden (gekürzt)"
    )
    for task in (improve, examples, draft, diagnose):
        task.add_argument("--yes", "-y", action="store_true", help="Senden bestätigen")
        task.add_argument(
            "--preview-file", type=Path, help="Datenvorschau in diese Datei (0600) statt stdout"
        )
    for task in (improve, examples, draft):
        task.add_argument(
            "--apply", action="store_true", help="Ergebnis ohne Rückfrage in den Benutzerordner"
        )
    args = parser.parse_args(argv)
    try:
        return _dispatch(parser, args)
    except BrokenPipeError:
        # Reader (e.g. head) closed early: not an error. Point stdout at devnull so the
        # interpreter's final flush does not fail again.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0


def _catalog(registry: ModuleRegistry | None = None, *, sandbox: bool = True) -> Catalog:
    """Catalog that fetches help in the sandbox when it is available (host otherwise)."""
    return Catalog(registry=registry, sandbox=self_test() if sandbox else None)


def _dispatch(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if args.command == "tools":
        needle = (args.search or "").lower()
        for tool in Catalog().tools():
            if needle in tool.name.lower():
                print(f"{tool.name}\t{tool.path}")
        return 0
    if args.command == "inspect":
        registry = _registry()
        for err in registry.errors:
            print(f"WARNUNG {err}", file=sys.stderr)
        try:
            info = _catalog(registry, sandbox=not args.no_sandbox).get(
                args.tool,
                args.sub,
                refresh=args.refresh,
                depth=1 if args.deep else 0,
                probe_unknown=True,
            )
        except ToolNotFound as err:
            print(err, file=sys.stderr)
            return 1
        except (OSError, ValidationError) as err:
            print(
                f"Tool '{args.tool}' konnte nicht gelesen werden: {err}. "
                "Prüfe Rechte und Cache-Ordner oder nutze --refresh.",
                file=sys.stderr,
            )
            return 1
        print(info.model_dump_json(indent=2) if args.json else _format_info(info))
        return 0
    if args.command == "validate":
        return _validate(args.files)
    if args.command == "scaffold":
        return _scaffold(args)
    if args.command == "modules":
        return _modules(args.watch)
    if args.command == "workflows":
        return _workflows()
    if args.command == "run":
        return _run(args)
    if args.command == "sandbox":
        return _sandbox()
    if args.command == "example":
        return _example(args)
    if args.command == "gui":
        return _gui(args)
    if args.command == "ai":
        return _ai(args)
    if args.command == "terminal":
        return _transcripts(args.delete)
    if args.command == "schema":
        try:
            written = export_schemas(args.out)
        except OSError as err:
            print(
                f"Schemas konnten nicht geschrieben werden: {err}. "
                f"Prüfe, ob der Ordner {args.out} beschreibbar ist.",
                file=sys.stderr,
            )
            return 1
        for path in written:
            print(f"geschrieben: {path}")
        return 0
    parser.print_help()
    return 0


def _ai(args: argparse.Namespace) -> int:
    try:
        settings = load_settings()
    except DocumentError as err:
        print(f"{err}\nEinstellungsdatei korrigieren oder löschen.", file=sys.stderr)
        return 1
    try:
        if args.ai_command in ("enable", "disable", "status", "config"):
            return _ai_settings(args, settings)
        if args.ai_command == "check":  # reports "KI aus" itself, imports providers only when on
            result = check(settings, probe_network=not args.no_network)
            _print_check(result)
            return 0 if result.ok else 1
        require_enabled(settings)  # first thing for every task: no catalog, file or network access
        return _ai_task(args, settings)
    except AiDisabled as err:
        print(err, file=sys.stderr)
        return 2


def _ai_settings(args: argparse.Namespace, settings: Settings) -> int:
    if args.ai_command == "status":
        ai = settings.ai
        key = ai.api.key_env
        source = (
            f"ENV {key} ({'gesetzt' if os.environ.get(key) else 'nicht gesetzt'})"
            if ai.api.key_source == "env"
            else "Schlüsselbund"
        )
        print(f"KI: {'an' if ai.enabled else 'aus'}, Anbieter: {ai.provider}")
        print(f"local: {ai.local.base_url} Modell '{ai.local.model}'")
        print(f"api: {ai.api.kind} Modell '{ai.api.model}' Schlüsselquelle {source}")
        print(f"agent: {ai.agent.kind} Aufruf {ai.agent.command or 'Standard'}")
        print(f"Befehlsausgaben mitsenden: {'ja' if ai.send_outputs else 'nein'}")
        print("Prüfung der Quelle: `wts ai check`")
        return 0
    data = settings.model_dump(mode="json")
    if args.ai_command == "config":
        node = data["ai"]
        *parents, leaf = args.path.split(".")
        for part in parents:
            node = node.get(part) if isinstance(node, dict) else None
        if not isinstance(node, dict) or leaf not in node:
            print(
                f"Unbekannter Pfad '{args.path}'. Gültig sind z. B. provider, send_outputs, "
                "local.model, api.model, api.key_env, agent.kind. "
                "Schlüssel gehören nie in Dateien.",
                file=sys.stderr,
            )
            return 1
        try:
            node[leaf] = json.loads(args.value)
        except json.JSONDecodeError:
            node[leaf] = args.value
    else:
        data["ai"]["enabled"] = args.ai_command == "enable"
    try:
        settings = Settings.model_validate(data)
        save_settings(settings)
    except ValidationError as err:  # no input values in the message: it may be a key
        for item in err.errors():
            where = ".".join(str(p) for p in item["loc"])
            print(f"Ungültiger Wert für {where}: {item['msg']}", file=sys.stderr)
        return 1
    except OSError as err:
        print(f"Einstellungen nicht schreibbar: {err}. Prüfe Rechte auf {paths.config_dir()}.")
        return 1
    print(f"KI: {'an' if settings.ai.enabled else 'aus'} ({args.ai_command})")
    return 0


def _print_check(result: CheckResult) -> None:
    try:
        "✔✘".encode(sys.stdout.encoding or "ascii")
        good, bad = "✔", "✘"
    except (UnicodeEncodeError, LookupError):
        good, bad = "[ok]", "[fehlt]"
    for item in result.items:
        print(f"{good if item.ok else bad} {item.name}: {item.detail}")
        if item.hint:
            print(f"    {item.hint}")
    state = "bereit" if result.ok else "nicht bereit"
    print(f"KI-Quelle '{result.provider}': {state}")


def _preview_text(prompt: Prompt, provider: str) -> str:
    def part(title: str, text: str) -> str:
        return f"--- {title} ({len(text.splitlines())} Zeilen, {len(text)} Zeichen) ---\n{text}"

    total = len(prompt.system) + len(prompt.user)
    return "\n".join(
        [
            f"== Datenvorschau: Das wird an den Anbieter '{provider}' gesendet ==",
            f"Gesamtlänge: {total} Zeichen",
            part("System", prompt.system),
            part("Nutzer", prompt.user),
            "== Ende der Datenvorschau ==",
        ]
    )


def _confirm(question: str, *, yes: bool) -> bool | None:
    """True/False for the answer, None when a question is needed but there is no terminal."""
    if yes:
        return True
    if not sys.stdin.isatty():
        return None
    return _ask(question)


def _read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _ai_prompt(
    args: argparse.Namespace, settings: Settings, registry: ModuleRegistry
) -> tuple[Prompt, Literal["module", "workflow", "text"], Path | None, str | None]:
    """Build the prompt; returns it with the kind, the target file and the current text."""
    command = args.ai_command
    if command == "diagnose":
        step = json.loads(args.run_json.read_text(encoding="utf-8"))["results"][args.step_id]
        include = args.include_output or settings.ai.send_outputs
        return ai_tasks.diagnose(step, include), "text", None, None
    if command == "draft-workflow":
        target = Path(f"{args.name}.workflow.yaml") if args.name else None
        if target is not None:
            target_path("workflow", target)  # reject bad names before anything is sent
        hint = "\n".join(
            f"{m.module.tool}: " + ", ".join(f.id for f in (*m.module.inputs, *m.module.options))
            for m in registry.all()
        )
        return ai_tasks.draft_workflow(args.description, hint), "workflow", target, None
    target = args.out if command == "improve-module" and args.out else None
    target = target or Path(f"{args.tool}.module.yaml")
    existing = target_path("module", target)  # target check before any read
    info = _catalog(registry).get(args.tool, probe_unknown=True)
    current = _read_text(existing)
    if current is None:  # no user file: the effective (e.g. bundled) module is the baseline
        current = registry_module_text(args.tool, registry)
    inspect_json = info.model_dump_json(exclude_none=True)  # compact: one line in the prompt
    if command == "improve-module":
        prompt = ai_tasks.improve_module(
            args.tool,
            current_raw=current,
            inspect_json=inspect_json,
        )
    else:
        prompt = ai_tasks.generate_examples(
            args.tool, current or scaffold_module(info), inspect_json
        )
    return prompt, "module", target, current


def _ai_task(args: argparse.Namespace, settings: Settings) -> int:
    try:
        prompt, kind, target, current = _ai_prompt(args, settings, _registry())
    except ToolNotFound as err:
        print(err, file=sys.stderr)
        return 1
    except ValueError as err:
        if args.ai_command != "diagnose":
            print(f"Ungültiges Ziel: {err}", file=sys.stderr)
            return 1
        print(
            f"RUN.json ungültig: {err}. Erwartet ist die Ausgabe von `wts run --json`.",
            file=sys.stderr,
        )
        return 1
    except (OSError, ValidationError, KeyError, TypeError) as err:
        print(
            f"Eingabe nicht lesbar: {err!r}. Prüfe Tool, Dateipfad und Schritt-ID "
            "(RUN.json stammt von `wts run --json`).",
            file=sys.stderr,
        )
        return 1

    secrets = ai_tasks.known_keys(settings.ai.api.key_env)
    prompt = Prompt(
        mask_text(prompt.system, secrets), mask_text(prompt.user, secrets), prompt.max_tokens
    )
    preview = _preview_text(prompt, settings.ai.provider)
    if args.preview_file:
        try:
            atomic_write(args.preview_file, preview + "\n", 0o600)
        except OSError as err:
            print(f"Vorschau nicht schreibbar: {err}. Anderen Pfad wählen.", file=sys.stderr)
            return 1
        print(f"Datenvorschau geschrieben: {args.preview_file}")
    else:
        print(preview)
    sent = _confirm("Senden? [j/N] ", yes=args.yes)
    if sent is None:
        print("Bestätigung nötig, aber kein Terminal: mit --yes bestätigen.", file=sys.stderr)
        return 2
    if not sent:
        print("Abgebrochen, nichts gesendet.", file=sys.stderr)
        return 2
    try:
        answer = make_provider(settings).complete(prompt)
    except ImportError as err:
        print(
            f"KI-Anbieter nicht verfügbar: {ai_tasks.sanitize(str(err), secrets)}", file=sys.stderr
        )
        return 1
    except (RuntimeError, OSError) as err:
        print(
            f"Anbieter fehlgeschlagen: {ai_tasks.sanitize(str(err), secrets)}. "
            "Prüfe Einstellungen mit `wts ai status`.",
            file=sys.stderr,
        )
        return 1
    if kind == "text":
        print(ai_tasks.sanitize(answer, secrets))  # untrusted: no key echo, no terminal escapes
        return 0
    return _ai_approve(args, kind, target, current, ai_tasks.extract_yaml(answer), secrets)


def _free_workflow_target(args: argparse.Namespace, name: str) -> Path:
    """Target of a draft: `--name`, else a free name derived from the workflow name."""
    if args.name:
        return Path(f"{args.name}.workflow.yaml")
    stem = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workflow"
    candidate = Path(f"{stem}.workflow.yaml")
    number = 2
    while (user_dir("workflow") / candidate).exists() or (
        user_dir("workflow") / candidate
    ).is_symlink():
        candidate = Path(f"{stem}_{number}.workflow.yaml")
        number += 1
    if candidate.name != f"{stem}.workflow.yaml":
        print(
            f"{stem}.workflow.yaml existiert bereits und bleibt unberührt; Vorschlag als "
            f"{candidate.name}. Zum Überschreiben --name {stem} angeben."
        )
    return candidate


def _ai_approve(
    args: argparse.Namespace,
    kind: Literal["module", "workflow"],
    target: Path | None,
    current: str | None,
    raw: str,
    secrets: list[str],
) -> int:
    try:
        if kind == "module":
            module, errors = validate_module_text(raw)
            if module is not None and module.tool != args.tool:
                errors.append(f"tool ist '{module.tool}', erwartet '{args.tool}'")
        else:
            workflow, errors = validate_workflow_text(raw)
            if workflow is not None:
                target = _free_workflow_target(args, workflow.name)
                current = _read_text(target_path("workflow", target))  # diff against the real file
    except (ValueError, OSError) as err:
        print(f"Ziel nicht nutzbar: {err}", file=sys.stderr)
        return 1
    approval = propose(kind, target, current, raw, errors)
    if errors:
        print("Die Antwort besteht die Schema-Prüfung nicht, nichts gespeichert:", file=sys.stderr)
        for line in errors:
            print(f"  {ai_tasks.sanitize(line, secrets)}", file=sys.stderr)
        return 1
    if current is None:
        print(ai_tasks.sanitize(raw, secrets))
    elif approval.diff:
        print(ai_tasks.sanitize(approval.diff, secrets))
    else:
        print("Keine Änderung.")
        return 0
    if not args.apply:
        if not sys.stdin.isatty():
            print("Nichts gespeichert. Mit --apply übernehmen.", file=sys.stderr)
            return 0
        if not _ask("Übernehmen? [j/N] "):
            print("Nicht übernommen.", file=sys.stderr)
            return 2
    try:
        print(f"geschrieben: {apply(approval)}")
    except (ValueError, OSError) as err:
        print(f"Nicht gespeichert: {err}", file=sys.stderr)
        return 1
    return 0


def _serve(app: Any, sock: socket.socket) -> None:
    import asyncio

    import uvicorn

    config = uvicorn.Config(
        app,
        log_level="warning",
        access_log=False,
        ws_max_size=1_048_576,
        timeout_graceful_shutdown=3,
    )
    server = uvicorn.Server(config)
    app.state.request_shutdown = lambda: setattr(server, "should_exit", True)
    asyncio.run(server.serve(sockets=[sock]))


def _write_redirect(port: int, url: str) -> Path:
    """Write a private page that forwards to `url`, so the token never shows in `ps`."""
    directory = paths.cache_dir() / "gui"
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    target = directory / f"open-{port}.html"
    target.unlink(missing_ok=True)
    shown = html.escape(url)
    page = (
        f'<!doctype html><meta http-equiv="refresh" content="0;url={shown}">'
        f'<a href="{shown}">WhatTheShell öffnen</a>\n'
    )
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(page)
    return target


def _open_browser(url: str, port: int) -> None:
    """Open `url` through a private redirect page so the token stays out of `ps`."""
    webbrowser.open(_write_redirect(port, url).as_uri())


def _running() -> instance.InstanceInfo | None:
    found = instance.read()
    return found if found is not None and instance.is_alive(found) else None


def _desktop_quote(arg: str) -> str:
    """Quote one Exec argument per the Desktop Entry spec (two escaping levels)."""
    arg = arg.replace("%", "%%")
    if re.search(r"[\s\"'\\><~|&;$*?#()`%]", arg):
        for char in ("\\", '"', "`", "$"):
            arg = arg.replace(char, "\\" + char)
        arg = f'"{arg}"'
    return arg.replace("\\", "\\\\")


def _install_desktop() -> int:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    target = Path(base) / "applications" / "whattheshell.desktop"
    entry = (
        "[Desktop Entry]\nType=Application\nName=WhatTheShell\n"
        "Comment=Grafischer Baukasten für Terminal-Workflows\n"
        f"Exec={_desktop_quote(sys.executable)} -m whattheshell gui start\nTerminal=false\n"
        "Categories=Utility;System;\nIcon=utilities-terminal\n"
    )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(entry, encoding="utf-8")
    except OSError as err:
        print(f"Menüeintrag nicht geschrieben: {err}", file=sys.stderr)
        return 1
    print(f"Menüeintrag geschrieben: {target}")
    updater = shutil.which("update-desktop-database")
    if updater:
        subprocess.run([updater, str(target.parent)], check=False)  # noqa: S603
    return 0


def _gui_start(args: argparse.Namespace) -> int:
    found = _running()
    if found is None:
        log = paths.cache_dir() / "gui.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        except OSError as err:
            print(f"Log {log} nicht schreibbar: {err}", file=sys.stderr)
            return 1
        with os.fdopen(fd, "ab") as out:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "whattheshell",
                    "gui",
                    "--no-browser",
                    "--port",
                    str(args.port),
                ],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=out,
                close_fds=True,
            )
        deadline = time.monotonic() + 10
        while found is None and time.monotonic() < deadline:
            time.sleep(0.1)
            found = _running()
        if found is None:
            print(f"Server nicht gestartet. Ursache im Log: {log}", file=sys.stderr)
            return 1
        print(found.url, flush=True)
    else:
        print(f"Läuft bereits auf Port {found.port} (PID {found.pid})")
    if not args.no_browser:
        _open_browser(found.url, found.port)
    return 0


def _gui_stop() -> int:
    found = instance.read()
    if found is None or not instance.is_alive(found):
        if found is not None:
            instance.clear(found)
        print("Nicht gestartet")
        return 0
    if not instance.stop(found):
        print(
            f"PID {found.pid} lässt sich nicht beenden. Manuell: kill -9 {found.pid}",
            file=sys.stderr,
        )
        return 1
    instance.clear(found)
    print("Beendet")
    return 0


def _gui_status() -> int:
    found = _running()
    if found is None:
        print("Nicht gestartet")
        return 3
    print(
        f"Läuft auf Port {found.port} (PID {found.pid}), seit {int(time.time() - found.started)} s"
    )
    return 0


def _on_sigterm(signum: int, frame: Any) -> None:
    raise KeyboardInterrupt


def _gui(args: argparse.Namespace) -> int:
    if args.install_desktop:
        return _install_desktop()
    if args.action == "stop":
        return _gui_stop()
    if args.action == "status":
        return _gui_status()
    if os.geteuid() == 0:
        print(
            "Start als root wird verweigert: die Oberfläche kann Befehle ausführen. "
            "Starte als normaler Benutzer.",
            file=sys.stderr,
        )
        return 1
    if args.action == "start":
        return _gui_start(args)
    try:
        lock = instance.acquire_lock()
    except OSError as err:
        print(f"Instanzsperre nicht möglich: {err}", file=sys.stderr)
        return 1
    if lock is None:  # another server holds it for its whole lifetime
        found = _running()
        if found is None:
            print("Läuft bereits (Zustand noch nicht lesbar), `wts gui status` prüft.")
        else:
            print(f"Läuft bereits auf Port {found.port} (PID {found.pid})")
            if not args.no_browser:
                _open_browser(found.url, found.port)
        return 0
    from whattheshell.api.app import STATIC_DIR, create_app
    from whattheshell.api.security import Session

    # bind first and hand the socket to uvicorn: no window in which another process takes the port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    port = 0
    mine: instance.InstanceInfo | None = None
    try:
        try:
            sock.bind(("127.0.0.1", args.port))
        except OSError as err:
            print(
                f"Port {args.port} nicht nutzbar: {err}. Anderen Port mit --port wählen.",
                file=sys.stderr,
            )
            return 1
        sock.listen()
        port = sock.getsockname()[1]
        registry = _registry()
        for problem in registry.errors:
            print(f"WARNUNG {problem}", file=sys.stderr)
        session = Session(port=port)
        app = create_app(session, catalog=Catalog(registry=registry), registry=registry)
        if not (STATIC_DIR / "index.html").is_file():
            print(
                "Hinweis: Frontend nicht gebaut (cd gui && npm ci && npm run build); "
                "die Seite zeigt nur eine Fehlermeldung, die API läuft.",
                file=sys.stderr,
            )
        url = f"http://127.0.0.1:{port}/#token={session.token}"
        if sys.stdout.isatty():  # `gui start` reads the URL from gui.json, not from a log
            print(url, flush=True)
        mine = instance.InstanceInfo(
            os.getpid(), port, url, time.time(), instance.own_start_ticks()
        )
        try:
            instance.write(mine)
        except OSError as err:
            print(
                f"Zustandsdatei nicht geschrieben: {err}. Ohne sie lässt sich die Instanz "
                "nicht beenden oder erkennen; Server wird nicht gestartet.",
                file=sys.stderr,
            )
            return 1
        if not args.no_browser:
            webbrowser.open(_write_redirect(port, url).as_uri())
        # uvicorn restores this handler after its own shutdown and re-raises SIGTERM into it
        signal.signal(signal.SIGTERM, _on_sigterm)
        with contextlib.suppress(KeyboardInterrupt):
            _serve(app, sock)
    finally:
        sock.close()
        if mine is not None:
            instance.clear(mine)
        (paths.cache_dir() / "gui" / f"open-{port}.html").unlink(missing_ok=True)
        os.close(lock)
    return 0


def _validate(files: list[Path]) -> int:
    failed = 0
    for path in files:
        try:
            if path.name.endswith(MODULE_SUFFIXES):
                kind, label = "Modul", load_module_file(path).tool
            elif path.name.endswith(WORKFLOW_SUFFIXES):
                kind, label = "Workflow", load_workflow_file(path).name
            else:
                raise DocumentError(
                    path, None, "Unbekannter Dateityp, erwartet *.module.yaml oder *.workflow.yaml"
                )
        except DocumentError as err:
            failed += 1
            print(err, file=sys.stderr)
        else:
            print(f"OK: {path} ({kind} {label})")
    print(f"{len(files)} Dateien geprüft, {failed} fehlerhaft")
    return 1 if failed else 0


def _scaffold(args: argparse.Namespace) -> int:
    out: Path | None = args.out
    if args.user:
        name = ".".join([Path(args.tool).name, *args.sub])
        out = paths.config_dir() / "modules" / f"{name}.module.yaml"
    try:
        text = scaffold_module(_catalog().get(args.tool, args.sub))
        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w" if args.force else "x", encoding="utf-8") as handle:
                handle.write(text)
            print(f"geschrieben: {out}")
            return 0
    except ToolNotFound as err:
        print(err, file=sys.stderr)
        return 1
    except FileExistsError:
        suggestion = paths.config_dir() / "modules" / f"{args.tool}.module.yaml"
        print(
            f"{out} existiert bereits. Nutze --force zum Überschreiben oder "
            f"wähle einen anderen Namen, z. B. {suggestion}.",
            file=sys.stderr,
        )
        return 1
    except OSError as err:
        print(f"Gerüst für '{args.tool}' nicht lesbar oder schreibbar: {err}", file=sys.stderr)
        return 1
    print(text, end="")
    return 0


def _sandbox() -> int:
    status = self_test()
    if status.available:
        print(f"Sandbox verfügbar: {status.bwrap_path}")
        return 0
    print(f"Sandbox nicht verfügbar: {status.reason}")
    if status.install_hint:
        print(f"Installieren: {status.install_hint}")
    return 1


def _print_example(number: int, result: ExampleResult) -> bool:
    print(f"Beispiel {number}: {result.title}")
    print(f"  $ {result.command}")
    for line in result.stdout.splitlines():
        print(f"  | {line}")
    for line in result.stderr.splitlines():
        print(f"  ! {line}")
    ok = not result.failures
    code = "nicht gestartet" if result.exit_code is None else f"exit {result.exit_code}"
    print(f"  [{'ok' if ok else 'FEHLER'} {code}, {result.duration:.2f}s]")
    for failure in result.failures:
        print(f"  -> {failure}")
    return ok


def _example(args: argparse.Namespace) -> int:
    if args.all and args.number is not None:
        print("--all und eine Nummer schließen sich aus.", file=sys.stderr)
        return 3
    registry = _registry()
    try:
        info = _catalog(registry).get(args.tool)
    except ToolNotFound as err:
        print(err, file=sys.stderr)
        return 1
    except (OSError, ValidationError) as err:
        print(f"Tool '{args.tool}' konnte nicht gelesen werden: {err}", file=sys.stderr)
        return 1
    examples = info.command.examples
    if not examples:
        print(f"Keine Beispiele für '{args.tool}' (kein Modul mit examples).")
        return 0
    if args.number is not None and not 1 <= args.number <= len(examples):
        print(
            f"Beispiel {args.number} gibt es nicht, vorhanden: 1 bis {len(examples)}.",
            file=sys.stderr,
        )
        return 3
    status = self_test()
    if not status.available:
        print(f"Sandbox nicht verfügbar: {status.reason}", file=sys.stderr)
        if status.install_hint:
            print(f"Installieren: {status.install_hint}", file=sys.stderr)
        return 2
    chosen = (
        [(args.number, examples[args.number - 1])]
        if args.number is not None
        else list(enumerate(examples, 1))
    )
    results = [_print_example(n, run_example(info, e, status=status)) for n, e in chosen]
    return 0 if all(results) else 1


def _ask(prompt: str) -> bool:
    sys.stderr.write(prompt)
    sys.stderr.flush()
    return sys.stdin.readline().strip().lower() in ("j", "ja", "y", "yes")


def _pick(prompt: str, options: list[str], current: str | None = None) -> str | None:
    """Numbered choice (number or option); empty keeps `current`; None on EOF."""
    for number, option in enumerate(options, 1):
        sys.stderr.write(f"  {number}) {printable(option)}\n")
    while True:
        sys.stderr.write(prompt)
        sys.stderr.flush()
        line = sys.stdin.readline()
        if not line:
            return None
        answer = line.strip()
        if not answer and current:
            return current
        if answer in options:
            return answer
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        sys.stderr.write("Ungültige Auswahl. Nummer oder Wert eingeben.\n")


def _ask_form(request: AskRequest) -> AskAnswer | None:
    """Terminal asker for `ask` steps; EOF on stdin or getpass cancels."""
    try:
        return _read_form(request)
    except EOFError:
        return None


def _read_form(request: AskRequest) -> AskAnswer | None:
    if request.error:
        sys.stderr.write(f"Fehler: {printable(request.error)}\n")
    if request.title:
        sys.stderr.write(f"{printable(request.title)}\n")
    if request.text:
        sys.stderr.write(f"{printable(request.text, keep_newlines=True)}\n")
    values: dict[str, Any] = {}
    for name, spec in request.fields.items():
        label = printable(f"{spec.label} ({name})" if spec.label else name)
        if spec.help:
            sys.stderr.write(f"{printable(spec.help, keep_newlines=True)}\n")
        current = request.current.get(name)
        shown = f" [{printable(current)}]" if current else ""
        if spec.type is ValueType.secret:
            sys.stderr.flush()
            entered = getpass.getpass(f"{label}: ")
        elif spec.type is ValueType.enum and spec.choices:
            picked = _pick(f"{label}{shown}: ", spec.choices, current)
            if picked is None:
                return None
            entered = picked
        else:
            hint = " [j/n]" if spec.type is ValueType.bool else ""
            sys.stderr.write(f"{label}{hint}{shown}: ")
            sys.stderr.flush()
            line = sys.stdin.readline()
            if not line:
                return None
            entered = line.strip()
            if spec.type is ValueType.bool and entered.lower() in ("j", "ja", "n", "nein"):
                entered = "true" if entered.lower() in ("j", "ja") else "false"
        if entered:  # empty keeps the current/default value
            values[name] = entered
    button = request.buttons[0]
    if len(request.buttons) > 1:
        picked = _pick("Knopf: ", request.buttons)
        if picked is None:
            return None
        button = picked
    return AskAnswer(values, button)


def _print_event(event: Event) -> None:
    match event:
        case StepStarted():
            print(f">> {event.step_id} ({event.safety.value}): {event.command}", flush=True)
        case OutputChunk():
            prefix = "  | " if event.stream == "stdout" else "  ! "
            for line in event.text.splitlines():
                print(prefix + printable(line, keep_newlines=True), flush=True)
        case StepFinished():
            state = "ok" if event.ok else "FEHLER"
            code = "nicht gestartet" if event.exit_code is None else f"exit {event.exit_code}"
            retry = f", Versuch {event.attempt}" if event.attempt > 1 else ""
            print(f"   [{state} {code}, {event.duration:.2f}s{retry}]", flush=True)
        case Message():
            print(f"   # {printable(event.text, keep_newlines=True)}", flush=True)
        case StepSkipped():
            print(f"-- {event.step_id} übersprungen: {event.reason}", flush=True)
        case WorkflowFinished():
            print(f"== {event.status}: {event.message}", flush=True)


def _parse_vars(items: list[str]) -> dict[str, str] | None:
    pairs = [item.partition("=") for item in items]
    if any(not name or not sep for name, sep, _ in pairs):
        return None
    return {name: value for name, _, value in pairs}


def _execute(runner: Runner, prepared: Prepared, controller: Controller) -> RunResult | None:
    """Run in a worker thread so Ctrl-C can abort cleanly (the runner kills the process group)."""
    outcome: list[RunResult] = []
    failure: list[BaseException] = []

    def work() -> None:
        try:
            outcome.append(runner.run(prepared))
        except BaseException as err:  # noqa: BLE001 (re-raised in the main thread)
            failure.append(err)

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    try:
        while worker.is_alive():
            worker.join(0.2)
    except KeyboardInterrupt:
        controller.abort.set()
        worker.join(5)  # a worker blocked on a prompt is left behind as daemon
    if failure:
        raise failure[0]
    return outcome[0] if outcome else None


def _workflow_index() -> WorkflowIndex:
    index = WorkflowIndex(paths.workflow_dirs(Path.cwd()))
    index.scan()
    return index


def _transcripts(delete: str | None) -> int:
    from whattheshell.api.terminal import delete_transcript, list_transcripts

    if delete is None:
        for item in list_transcripts():
            print(f"{item['name']}\t{item['size']}")
        return 0
    try:
        delete_transcript(delete)
    except (ValueError, OSError) as err:
        print(err, file=sys.stderr)
        return 1
    return 0


def _workflows() -> int:
    for entry in sorted(_workflow_index().all(), key=lambda e: e.id):
        if entry.error:
            print(f"FEHLER {entry.error}", file=sys.stderr)
        else:
            print(f"{entry.source}\t{entry.id}\t{entry.name}\t{entry.steps}\t{entry.path}")
    return 0


def _run(args: argparse.Namespace) -> int:
    file: Path = args.file
    entry = _workflow_index().get(str(file)) if len(file.parts) == 1 else None
    if not file.exists() and entry is not None:  # not a path: use the library entry
        file = entry.path
        print(f"Quelle {entry.source}: {file}", file=sys.stderr)
    try:
        workflow = load_workflow_file(file)
    except DocumentError as err:
        print(err, file=sys.stderr)
        if entry is not None and file == args.file:
            print(
                f"Hinweis: Der Pfad '{file}' hat Vorrang vor der Workflow-id gleichen Namens "
                f"({entry.path}, Quelle {entry.source}). Pfad umbenennen, um die id zu nutzen.",
                file=sys.stderr,
            )
        return 3
    overrides = _parse_vars(args.var)
    if overrides is None:
        print("--var erwartet NAME=WERT, z. B. --var logdir=./logs", file=sys.stderr)
        return 3
    cwd: Path = (args.cwd or Path.cwd()).resolve()
    if not cwd.is_dir():
        print(
            f"Arbeitsverzeichnis {cwd} existiert nicht. Mit --cwd ein vorhandenes angeben.",
            file=sys.stderr,
        )
        return 3
    registry = _registry()
    for problem in registry.errors:
        print(f"WARNUNG {problem}", file=sys.stderr)
    controller = Controller()
    broken = threading.Event()

    def on_event(event: Event) -> None:
        try:
            _print_event(event)
        except BrokenPipeError:
            broken.set()
            controller.abort.set()  # stop the run instead of leaving processes behind

    def confirm(request: ConfirmRequest) -> bool:
        if args.yes:
            return True
        reasons = f" ({'; '.join(request.reasons)})" if request.reasons else ""
        return _ask(
            f"Schritt '{request.step_id}' ({request.safety.value}){reasons}: {request.command}\n"
            "Ausführen? [j/N] "
        )

    runner = Runner(
        _catalog(registry),
        confirm=confirm,
        ask=_ask_form,
        on_event=None if args.json else on_event,
        controller=controller,
        cwd=cwd,
    )
    try:
        prepared = runner.prepare(workflow, overrides)
    except RunError as err:
        print(err, file=sys.stderr)
        return 3
    overview = plan_text(plan(prepared))
    if args.dry_run:
        print(overview)
        return 0
    if any(isinstance(step, TerminalStep) for step in iter_steps(workflow.steps)):
        print(TERMINAL_ONLY_GUI, file=sys.stderr)
        return 3
    if not sys.stdin.isatty() and any(isinstance(s, AskStep) for s in iter_steps(workflow.steps)):
        print("Abfrage-Schritt braucht ein Terminal oder die GUI.", file=sys.stderr)
        return 3
    print(overview, file=sys.stderr if args.json else sys.stdout, flush=True)
    risky = any(v.safety is not Safety.safe for v in prepared.verdicts.values())
    if risky and not args.yes:
        if not sys.stdin.isatty():
            print(
                "Bestätigung nötig, aber kein Terminal: mit --yes bestätigen oder --dry-run",
                file=sys.stderr,
            )
            return 2
        if not _ask("Workflow ausführen? [j/N] "):
            print("Abgebrochen.", file=sys.stderr)
            return 2
    try:  # a thread stuck in getpass must not leave the terminal without echo
        tty_state = termios.tcgetattr(0) if sys.stdin.isatty() else None
    except termios.error:
        tty_state = None
    try:
        result = _execute(runner, prepared, controller)
    finally:
        if tty_state is not None:
            termios.tcsetattr(0, termios.TCSADRAIN, tty_state)
    if broken.is_set():
        raise BrokenPipeError
    if result is None:
        print("Abgebrochen.", file=sys.stderr)
        return 2
    if args.json:
        text = json.dumps(dataclasses.asdict(result), default=lambda o: o.isoformat(), indent=2)
        # last line of defence: also catch secrets in their JSON-escaped form
        for secret in secret_values(workflow, prepared.variables):
            text = text.replace(json.dumps(secret)[1:-1], "***")
        print(mask_text(text, secret_values(workflow, prepared.variables)))
    return {"success": 0, "failed": 1}.get(result.status, 2)


def _modules(follow: bool) -> int:
    registry = _registry()
    for directory in registry.dirs:
        if not directory.is_dir():
            print(f"Suchpfad: {directory} (fehlt)")
        else:
            count = sum(1 for m in registry.all() if m.path.parent == directory)
            print(f"Suchpfad: {directory} ({count} Module)")
    for loaded in sorted(registry.all(), key=lambda m: (m.priority, m.module.tool)):
        print(f"{loaded.priority}\t{loaded.module.tool}\t{loaded.path}")
    for err in registry.errors:
        print(f"FEHLER {err}", file=sys.stderr)
    if not follow:
        return 0

    def report(changed: set[Path]) -> None:
        for path in sorted(changed):
            error = next((e for e in registry.errors if e.path == path), None)
            if not path.exists():
                print(f"entfernt: {path}", flush=True)
            elif error is None:
                print(f"neu geladen: {path}", flush=True)
            else:
                print(f"FEHLER {error}", file=sys.stderr, flush=True)

    def announce(pairs: list[tuple[Path, Path]]) -> None:
        for directory, watched in pairs:
            note = "" if directory == watched else f" (noch nicht vorhanden, Vorfahr {watched})"
            print(f"beobachte: {directory}{note}", flush=True)

    with contextlib.suppress(KeyboardInterrupt):
        watch_modules(registry, threading.Event(), report, announce)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
