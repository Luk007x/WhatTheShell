# SPDX-License-Identifier: AGPL-3.0-or-later
"""Auto-detected command catalog (not written by users)."""

from typing import Literal

from pydantic import Field

from whattheshell.models.common import Confidence, InputSpec, OptionSpec, Safety, StrictModel


class CommandSpec(StrictModel):
    """A command or subcommand, recursively."""

    name: list[str] = Field(min_length=1)
    summary: str | None = None
    usage: str | None = None
    inputs: list[InputSpec] = []
    options: list[OptionSpec] = []
    subcommands: list["CommandSpec"] = []
    raw_help: str | None = None
    confidence: Confidence = Confidence.high
    safety: Safety = Safety.safe
    interactive: bool = False


class ToolInfo(StrictModel):
    """Catalog entry of one installed tool."""

    name: str
    path: str
    version: str | None = None
    help_hash: str
    source: Literal["module", "help", "man", "fallback"]
    command: CommandSpec
