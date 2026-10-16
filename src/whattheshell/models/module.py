# SPDX-License-Identifier: AGPL-3.0-or-later
"""Module format: hand-written or AI-written overrides for the auto-detected catalog."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from whattheshell.i18n import _
from whattheshell.models.common import (
    InputSpec,
    OptionSpec,
    OutputKind,
    RelativePath,
    Safety,
    StrictModel,
    ToolName,
)


class StdoutSpec(StrictModel):
    """Interpretation of stdout."""

    kind: OutputKind = OutputKind.lines


class OutputSpec(StrictModel):
    """Output description of a command."""

    stdout: StdoutSpec = Field(default_factory=StdoutSpec)
    exit_codes: dict[int, str] = {}


class Fixture(StrictModel):
    """A file created in the sandbox before an example runs."""

    path: RelativePath
    content: str = ""


class Expect(StrictModel):
    """Expected result of an example."""

    exit_code: int | None = None
    stdout_contains: str | None = None
    stderr_contains: str | None = None
    stdout_regex: str | None = None

    @field_validator("stdout_regex")
    @classmethod
    def _compilable(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                re.compile(value)
            except re.error as err:
                raise ValueError(
                    _("stdout_regex ist kein gültiger regulärer Ausdruck: {err}", err=err)
                ) from err
        return value


class Example(StrictModel):
    """A runnable example."""

    title: str
    description: str | None = None
    fixtures: list[Fixture] = []
    args: dict[str, Any] = {}
    expect: Expect | None = None


class TemplateRef(StrictModel):
    """Reference to a workflow template, path relative to the module file."""

    title: str
    workflow: RelativePath


class FieldText(StrictModel):
    """Translated label and help."""

    label: str | None = None
    help: str | None = None


class Translation(StrictModel):
    """Translations for one language."""

    display_name: str | None = None
    summary: str | None = None
    description: str | None = None
    options: dict[str, FieldText] = {}
    inputs: dict[str, FieldText] = {}


class CommandOverride(StrictModel):
    """Fields shared by a module and its subcommands."""

    display_name: str | None = None
    category: str | None = None
    summary: str | None = None
    description: str | None = None
    safety: Safety | None = None
    interactive: bool | None = None
    inputs: list[InputSpec] = []
    options: list[OptionSpec] = []
    output: OutputSpec | None = None
    subcommands: list[Subcommand] = []
    examples: list[Example] = []
    i18n: dict[str, Translation] = {}

    @model_validator(mode="after")
    def _unique_names(self) -> CommandOverride:
        ids = [spec.id for spec in (*self.inputs, *self.options)]
        names = [sub.name for sub in self.subcommands]
        for kind, values in (
            (_("inputs/options-id"), ids),
            (_("subcommand-name"), names),
        ):
            for value in values:
                if values.count(value) > 1:
                    raise ValueError(
                        _("{kind} '{value}' kommt mehrfach vor", kind=kind, value=value)
                    )
        return self


class Subcommand(CommandOverride):
    """Override for one subcommand."""

    name: str


class Module(CommandOverride):
    """A tool module file."""

    schema_version: Literal[1]
    tool: ToolName
    override_mode: Literal["merge", "replace"] = "merge"
    templates: list[TemplateRef] = []


CommandOverride.model_rebuild()
Subcommand.model_rebuild()
Module.model_rebuild()
