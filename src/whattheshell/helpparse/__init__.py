# SPDX-License-Identifier: AGPL-3.0-or-later
"""Help parser: turn help text into a `CommandSpec`."""

from whattheshell.helpparse.clean import clean_text
from whattheshell.helpparse.parser import parse_help

__all__ = ["clean_text", "parse_help"]
