# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command line entry point."""

import argparse
import contextlib
import dataclasses
import json
import os
import sys
import threading
from pathlib import Path

from pydantic import ValidationError

from whattheshell import APP_NAME, __version__, paths
from whattheshell.catalog import Catalog, ToolNotFound
from whattheshell.engine import (
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
from whattheshell.models.common import Safety
from whattheshell.models.schema import export_schemas
from whattheshell.modules.loader import (
    MODULE_SUFFIXES,
    WORKFLOW_SUFFIXES,
    DocumentError,
    load_module_file,
    load_workflow_file,
)
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.modules.scaffold import scaffold_module
from whattheshell.modules.watch import watch_modules
from whattheshell.sandbox import ExampleResult, run_example, self_test


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
    run.add_argument("file", type=Path)
    run.add_argument("--dry-run", action="store_true", help="Nur den Plan zeigen")
    run.add_argument(
        "--yes", "-y", action="store_true", help="Alle Bestätigungen mit ja beantworten"
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
    modules = commands.add_parser("modules", help="Geladene Module auflisten")
    modules.add_argument("--watch", action="store_true", help="Änderungen live neu laden")
    args = parser.parse_args(argv)
    try:
        return _dispatch(parser, args)
    except BrokenPipeError:
        # Reader (e.g. head) closed early: not an error. Point stdout at devnull so the
        # interpreter's final flush does not fail again.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0


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
            info = Catalog(registry=registry).get(
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
    if args.command == "run":
        return _run(args)
    if args.command == "sandbox":
        return _sandbox()
    if args.command == "example":
        return _example(args)
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
        text = scaffold_module(Catalog().get(args.tool, args.sub))
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
        info = Catalog(registry=registry).get(args.tool)
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


def _print_event(event: Event) -> None:
    match event:
        case StepStarted():
            print(f">> {event.step_id} ({event.safety.value}): {event.command}", flush=True)
        case OutputChunk():
            prefix = "  | " if event.stream == "stdout" else "  ! "
            for line in event.text.splitlines():
                print(prefix + line, flush=True)
        case StepFinished():
            state = "ok" if event.ok else "FEHLER"
            code = "nicht gestartet" if event.exit_code is None else f"exit {event.exit_code}"
            retry = f", Versuch {event.attempt}" if event.attempt > 1 else ""
            print(f"   [{state} {code}, {event.duration:.2f}s{retry}]", flush=True)
        case Message():
            print(f"   # {event.text}", flush=True)
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


def _run(args: argparse.Namespace) -> int:
    try:
        workflow = load_workflow_file(args.file)
    except DocumentError as err:
        print(err, file=sys.stderr)
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
        Catalog(registry=registry),
        confirm=confirm,
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
    result = _execute(runner, prepared, controller)
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
