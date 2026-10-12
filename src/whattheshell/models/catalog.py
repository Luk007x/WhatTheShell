# SPDX-License-Identifier: AGPL-3.0-or-later
"""Auto-detected command catalog (not written by users)."""

from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from whattheshell.models.common import Confidence, InputSpec, OptionSpec, Safety, StrictModel
from whattheshell.models.module import Example, OutputSpec, TemplateRef, Translation


def unique_input_ids(inputs: Sequence[InputSpec], options: Sequence[OptionSpec]) -> list[InputSpec]:
    """Return the inputs with ids that collide with an option or earlier input suffixed ``_arg``."""
    taken = {option.id for option in options}
    result: list[InputSpec] = []
    for argument in inputs:
        new_id = argument.id
        while new_id in taken:
            new_id += "_arg"
        taken.add(new_id)
        result.append(
            argument if new_id == argument.id else argument.model_copy(update={"id": new_id})
        )
    return result


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
    display_name: str | None = None
    category: str | None = None
    description: str | None = None
    output: OutputSpec | None = None
    examples: list[Example] = []
    templates: list[TemplateRef] = []
    i18n: dict[str, Translation] = {}


class ToolInfo(StrictModel):
    """Catalog entry of one installed tool."""

    name: str
    path: str
    version: str | None = None
    help_hash: str
    source: Literal["module", "help", "man", "fallback"]
    command: CommandSpec
    module_files: list[str] = []
