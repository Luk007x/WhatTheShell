# SPDX-License-Identifier: AGPL-3.0-or-later
"""Building blocks shared by catalog and modules."""

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

ID_PATTERN = r"^[a-z][a-z0-9_]*$"

# No leading dash (option injection), no path separator.
ToolName = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")]


class StrictModel(BaseModel):
    """Base of all models: unknown fields are errors, so typos surface."""

    model_config = ConfigDict(extra="forbid")


def relative_path(value: str) -> str:
    """Check that a path is non-empty, relative and free of '..' segments.

    Raises:
        ValueError: If the path is empty, '.', absolute or contains '..'.
    """
    path = PurePosixPath(value)
    if str(path) == "." or path.is_absolute() or ".." in path.parts:
        raise ValueError("Pfad muss relativ sein, nicht leer und ohne '..'")
    return value


RelativePath = Annotated[str, AfterValidator(relative_path)]


class ValueType(StrEnum):
    """Type of an input field."""

    string = "string"
    int = "int"
    float = "float"
    bool = "bool"
    path = "path"
    enum = "enum"
    secret = "secret"


class Safety(StrEnum):
    """Safety class of a command or option."""

    safe = "safe"
    caution = "caution"
    dangerous = "dangerous"


class Confidence(StrEnum):
    """How sure the help parser was."""

    high = "high"
    medium = "medium"
    low = "low"


class Importance(StrEnum):
    """Sorting and collapsing hint for the GUI."""

    common = "common"
    normal = "normal"
    rare = "rare"


class OutputKind(StrEnum):
    """How stdout is to be interpreted."""

    lines = "lines"
    text = "text"
    json = "json"
    csv = "csv"
    bytes = "bytes"


class _FieldSpec(StrictModel):
    """Common base of option and input specs; only `id` is required."""

    id: str = Field(pattern=ID_PATTERN)
    label: str | None = None
    multiple: bool = False
    required: bool = False
    default: Any | None = None
    choices: list[str] = []
    min: float | None = None
    max: float | None = None
    metavar: str | None = None
    group: str | None = None
    importance: Importance = Importance.normal
    help: str | None = None
    safety: Safety | None = None  # None = inherits from the command
    confidence: Confidence = Confidence.high


class OptionSpec(_FieldSpec):
    """A command line option."""

    flags: list[str] = []
    type: ValueType = ValueType.bool
    attached: bool = False  # value glued on as --flag=value (long forms only)
    nargs: int = Field(1, ge=1)  # argv elements per occurrence


class InputSpec(_FieldSpec):
    """A positional argument."""

    type: ValueType = ValueType.string
    position: int | None = None
    before_options: bool = False  # argv: vor den Optionen (find PFAD -name …)
