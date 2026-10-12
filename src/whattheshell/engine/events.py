# SPDX-License-Identifier: AGPL-3.0-or-later
"""Events the runner reports while a workflow runs; texts are already masked."""

from dataclasses import dataclass
from typing import Literal

from whattheshell.models.common import Safety


@dataclass(frozen=True)
class StepStarted:
    """A command step is about to run."""

    step_id: str
    command: str
    safety: Safety


@dataclass(frozen=True)
class OutputChunk:
    """Decoded output of a running command (complete lines, except the last chunk)."""

    step_id: str
    stream: Literal["stdout", "stderr"]
    text: str


@dataclass(frozen=True)
class StepFinished:
    """One attempt of a command step ended."""

    step_id: str
    exit_code: int | None
    ok: bool
    duration: float
    attempt: int


@dataclass(frozen=True)
class StepSkipped:
    """A step was not executed."""

    step_id: str
    reason: str


@dataclass(frozen=True)
class Message:
    """Notice for the user (message step, warnings)."""

    step_id: str
    text: str


@dataclass(frozen=True)
class WorkflowFinished:
    """Last event of every run."""

    status: Literal["success", "failed", "aborted"]
    message: str


Event = StepStarted | OutputChunk | StepFinished | StepSkipped | Message | WorkflowFinished
