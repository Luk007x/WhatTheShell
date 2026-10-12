# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command line entry point."""

import argparse
import sys
from pathlib import Path

from whattheshell import APP_NAME, __version__
from whattheshell.models.schema import export_schemas


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
    args = parser.parse_args(argv)
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
