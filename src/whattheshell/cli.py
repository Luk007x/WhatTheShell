# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command line entry point."""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from whattheshell import APP_NAME, __version__
from whattheshell.catalog import Catalog, ToolNotFound
from whattheshell.models.catalog import CommandSpec, ToolInfo
from whattheshell.models.schema import export_schemas


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
            lines.append(_clip(f"  {', '.join(opt.flags)}  {opt.type}  {opt.confidence}  {first}"))
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
        f"{info.name} ({info.path}), {info.version or 'Version unbekannt'}, "
        f"Quelle {info.source}, Konfidenz {info.command.confidence}, "
        f"interaktiv {'ja' if info.command.interactive else 'nein'}"
    )
    return "\n".join([head, *_format_command(info.command)])


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
    args = parser.parse_args(argv)
    if args.command == "tools":
        needle = (args.search or "").lower()
        for tool in Catalog().tools():
            if needle in tool.name.lower():
                print(f"{tool.name}\t{tool.path}")
        return 0
    if args.command == "inspect":
        try:
            info = Catalog().get(
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


if __name__ == "__main__":
    raise SystemExit(main())
