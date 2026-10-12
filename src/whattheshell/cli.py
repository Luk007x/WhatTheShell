# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command line entry point."""

import argparse
import contextlib
import os
import sys
import threading
from pathlib import Path

from pydantic import ValidationError

from whattheshell import APP_NAME, __version__, paths
from whattheshell.catalog import Catalog, ToolNotFound
from whattheshell.models.catalog import CommandSpec, ToolInfo
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
                args.tool, args.sub, refresh=args.refresh, depth=1 if args.deep else 0
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
