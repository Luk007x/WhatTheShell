# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workflow format: a tree of steps; edges are derived, never stored."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator, Sequence
from typing import Annotated, Any, Literal

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from whattheshell.models.common import ID_PATTERN, StrictModel, ToolName, ValueType

logger = logging.getLogger(__name__)

_TEMPLATE = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)\s*\}\}")
_RESERVED_IDS = {"var", "item"}
_STEP_FIELDS = {"stdout", "stderr", "exit_code", "lines"}


class _Model(StrictModel):
    # Only the aliases `else`/`as` are valid, for reading and writing (lossless round trip).
    model_config = ConfigDict(serialize_by_alias=True)


class Stdin(_Model):
    """Standard input of a command: exactly one of pipe, text, file."""

    pipe: str | None = None
    text: str | None = None
    file: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Stdin:
        if (self.pipe, self.text, self.file).count(None) != 2:
            raise ValueError("stdin: genau eines von pipe, text, file setzen")
        return self


class Condition(_Model):
    """Condition with exactly one operator."""

    source: str
    eq: str | int | float | bool | None = None
    ne: str | int | float | bool | None = None
    contains: str | None = None
    regex: str | None = None
    is_empty: bool | None = None
    line_count_gt: int | None = None
    line_count_eq: int | None = None
    number_gt: float | None = None
    number_lt: float | None = None
    number_eq: float | None = None
    json_path: str | None = None
    file_exists: bool | None = None

    @field_validator("regex")
    @classmethod
    def _compilable(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                re.compile(value)
            except re.error as err:
                raise ValueError(f"regex ist kein gültiger regulärer Ausdruck: {err}") from err
        return value

    @property
    def operator(self) -> str:
        """Name of the one operator that is set."""
        return next(op for op in _OPERATORS if getattr(self, op) is not None)

    @model_validator(mode="after")
    def _exactly_one_operator(self) -> Condition:
        given = [op for op in _OPERATORS if getattr(self, op) is not None]
        if len(given) != 1:
            raise ValueError(
                f"condition: genau ein Operator erlaubt, gesetzt: {', '.join(given) or 'keiner'}"
            )
        return self


_OPERATORS = tuple(name for name in Condition.model_fields if name != "source")


class OnError(_Model):
    """Error handling of a command step."""

    action: Literal["abort", "continue", "retry", "fallback"] = "abort"
    retries: int | None = Field(default=None, ge=1)
    steps: Steps | None = None

    @model_validator(mode="after")
    def _action_fields(self) -> OnError:
        if (self.action == "retry") != (self.retries is not None):
            raise ValueError("on_error: retries ist genau bei action=retry Pflicht")
        if (self.action == "fallback") != (self.steps is not None):
            raise ValueError("on_error: steps ist genau bei action=fallback Pflicht")
        return self


def _not_reserved(value: str) -> str:
    if value in _RESERVED_IDS:
        raise ValueError(f"'{value}' ist reserviert")
    return value


class _Step(_Model):
    id: str = Field(pattern=ID_PATTERN)
    label: str | None = None

    _id_not_reserved = field_validator("id")(_not_reserved)


class CommandStep(_Step):
    """Runs an external program."""

    kind: Literal["command"] = "command"
    tool: ToolName
    command: list[Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")]] = []
    args: dict[str, Any] = {}
    extra_args: list[str] = []
    stdin: Stdin | None = None
    cwd: str | None = None
    env: dict[str, str] = {}
    timeout: float | None = Field(default=None, gt=0)
    ok_exit_codes: list[Annotated[int, Field(ge=0, le=255)]] = [0]
    on_error: OnError = Field(default_factory=OnError)


class IfStep(_Step):
    """Branch on a condition."""

    kind: Literal["if"]
    condition: Condition
    then: Steps
    else_: Steps | None = Field(default=None, alias="else")


class ForeachStep(_Step):
    """Iterate over the lines of a source."""

    kind: Literal["foreach"]
    source: str
    as_: str = Field(default="item", alias="as", pattern=ID_PATTERN)
    body: Steps

    _as_not_reserved = field_validator("as_")(_not_reserved)


class SetStep(_Step):
    """Set a variable."""

    kind: Literal["set"]
    variable: str = Field(pattern=ID_PATTERN)
    value: str


class WaitStep(_Step):
    """Delay."""

    kind: Literal["wait"]
    seconds: float = Field(ge=0)


class MessageStep(_Step):
    """Message to the user."""

    kind: Literal["message"]
    text: str


class AbortStep(_Step):
    """End the workflow."""

    kind: Literal["abort"]
    text: str | None = None
    exit_code: int = 1


Step = Annotated[
    CommandStep | IfStep | ForeachStep | SetStep | WaitStep | MessageStep | AbortStep,
    Field(discriminator="kind"),
]


def _default_kind(value: Any) -> Any:
    """Insert kind=command into step dicts that have `tool` but no `kind`."""
    if not isinstance(value, list):
        return value
    result = []
    for item in value:
        if isinstance(item, dict) and "kind" not in item:
            if "tool" not in item:
                raise ValueError(f"Schritt '{item.get('id', '?')}' braucht `kind` oder `tool`")
            item = {**item, "kind": "command"}
        result.append(item)
    return result


Steps = Annotated[list[Step], BeforeValidator(_default_kind)]


class VariableSpec(_Model):
    """A workflow variable."""

    type: ValueType = ValueType.string
    default: Any | None = None
    label: str | None = None
    help: str | None = None
    required: bool = False
    choices: list[str] = []
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _check_spec(self) -> VariableSpec:
        if self.type == ValueType.secret and self.default is not None:
            raise ValueError("Variable vom Typ secret darf keinen default haben")
        if self.choices and self.type != ValueType.enum:
            raise ValueError("choices ist nur bei type enum erlaubt")
        if (self.min is not None or self.max is not None) and self.type not in (
            ValueType.int,
            ValueType.float,
        ):
            raise ValueError("min und max sind nur bei type int oder float erlaubt")
        return self


class Position(_Model):
    """Node position in the graph view."""

    x: float
    y: float


class Layout(_Model):
    """Graph view positions, kept apart from the logic."""

    nodes: dict[str, Position] = {}


class Workflow(_Model):
    """A workflow file."""

    schema_version: Literal[1]
    name: str
    description: str | None = None
    variables: dict[Annotated[str, Field(pattern=ID_PATTERN)], VariableSpec] = {}
    steps: Steps
    layout: Layout | None = None

    @model_validator(mode="after")
    def _check(self) -> Workflow:
        ids: set[str] = set()
        for step in iter_steps(self.steps):
            if step.id in ids:
                raise ValueError(f"Schritt-id '{step.id}' kommt mehrfach vor")
            ids.add(step.id)
        for step in iter_steps(self.steps):
            if isinstance(step, ForeachStep) and step.as_ in ids:
                raise ValueError(f"Schritt '{step.id}': as '{step.as_}' überdeckt eine Schritt-id")
        _check_steps(self.steps, set(), frozenset(), set(self.variables), ids)
        if self.layout is not None:
            for unknown in [n for n in self.layout.nodes if n not in ids]:
                logger.warning("layout: unbekannte Schritt-id '%s' verworfen", unknown)
                del self.layout.nodes[unknown]
        return self


def _children(step: Step) -> list[Sequence[Step]]:
    if isinstance(step, IfStep):
        return [step.then, step.else_ or []]
    if isinstance(step, ForeachStep):
        return [step.body]
    if isinstance(step, CommandStep) and step.on_error.steps is not None:
        return [step.on_error.steps]
    return []


def iter_steps(steps: Sequence[Step]) -> Iterator[Step]:
    """Yield all steps depth first in document order."""
    for step in steps:
        yield step
        for child in _children(step):
            yield from iter_steps(child)


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


_OWN_FIELDS_ONLY: Any = {"then": True, "else_": True, "body": True, "on_error": {"steps": True}}


def _check_refs(
    step: Step, visible: set[str], names: frozenset[str], variables: set[str], ids: set[str]
) -> None:
    def fail(ref: str, why: str) -> None:
        raise ValueError(f"Schritt '{step.id}': Referenz '{ref}' {why}")

    def resolve(ref: str, allow_file: bool) -> None:
        if allow_file and ref.startswith("file:"):
            return
        head, _, tail = ref.partition(".")
        if not tail:
            if head not in names:
                fail(ref, "ist außerhalb eines passenden foreach unbekannt")
        elif head == "var":
            if tail not in variables:
                fail(ref, "nennt keine deklarierte Variable")
        elif head in visible:
            if tail not in _STEP_FIELDS:
                fail(ref, f"muss auf {'|'.join(sorted(_STEP_FIELDS))} enden")
        elif head in ids:
            fail(ref, f"zeigt auf '{head}', der nicht vorher steht")
        else:
            fail(ref, "ist unbekannt")

    if isinstance(step, SetStep) and step.variable not in variables:
        raise ValueError(f"Schritt '{step.id}' setzt undeklarierte Variable '{step.variable}'")
    if isinstance(step, IfStep):
        resolve(step.condition.source, allow_file=True)
    elif isinstance(step, ForeachStep):
        resolve(step.source, allow_file=True)
    elif isinstance(step, CommandStep) and step.stdin and step.stdin.pipe is not None:
        pipe = step.stdin.pipe
        if pipe not in visible:
            fail(pipe, "(stdin.pipe) ist kein vorheriger Schritt")
    for text in _strings(step.model_dump(exclude=_OWN_FIELDS_ONLY)):
        for opening in re.finditer(r"(?<!\\)\{\{", text):
            match = _TEMPLATE.match(text, opening.start())
            if match is None:
                raise ValueError(f"Schritt '{step.id}': ungültiges Template in {text!r}")
            resolve(match.group(1), allow_file=False)


def _check_steps(
    steps: Sequence[Step],
    visible: set[str],
    names: frozenset[str],
    variables: set[str],
    ids: set[str],
) -> None:
    visible = set(visible)
    for step in steps:
        _check_refs(step, visible, names, variables, ids)
        inner = names | {step.as_, "item"} if isinstance(step, ForeachStep) else names
        for child in _children(step):
            # a fallback sequence may reference the failed step itself
            is_fallback = isinstance(step, CommandStep) and child is step.on_error.steps
            _check_steps(
                child, visible | {step.id} if is_fallback else visible, inner, variables, ids
            )
        visible.add(step.id)


OnError.model_rebuild()
IfStep.model_rebuild()
ForeachStep.model_rebuild()
CommandStep.model_rebuild()
Workflow.model_rebuild()
