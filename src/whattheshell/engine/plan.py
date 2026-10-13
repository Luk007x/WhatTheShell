# SPDX-License-Identifier: AGPL-3.0-or-later
"""Dry run (F-21): list what a workflow would do, without starting any process."""

from collections.abc import Sequence
from dataclasses import dataclass

from whattheshell.engine.argv import ArgvError, build_argv
from whattheshell.engine.runner import (
    Prepared,
    describe,
    env_blocked,
    mask_text,
    secret_values,
)
from whattheshell.engine.template import Context, render, render_value
from whattheshell.models.common import Safety
from whattheshell.models.workflow import (
    AbortStep,
    CommandStep,
    Condition,
    ForeachStep,
    IfStep,
    MessageStep,
    SetStep,
    Step,
    TerminalStep,
    WaitStep,
)
from whattheshell.safety import Verdict, classify_command, merge_verdicts


@dataclass(frozen=True)
class PlannedLine:
    """One line of the plan; block headings (then, else, body, fallback) have no step_id."""

    indent: int
    kind: str
    step_id: str
    text: str
    safety: Safety | None = None
    reasons: tuple[str, ...] = ()


def _condition(cond: Condition) -> str:
    return f"{cond.source} {cond.operator} {getattr(cond, cond.operator)!r}"


def plan(prepared: Prepared) -> list[PlannedLine]:
    """Return the plan lines for the whole tree; secret values appear as ``***``."""
    secrets = secret_values(prepared.workflow, prepared.variables)
    variables = {k: mask_text(v, secrets) for k, v in prepared.variables.items()}
    ctx = Context(variables, {})
    lines: list[PlannedLine] = []

    def soft(text: str) -> str:
        return render(text, ctx, keep_unknown=True)

    def command(step: CommandStep | TerminalStep) -> tuple[str, Verdict]:
        info = prepared.specs[step.id]
        verdict = prepared.verdicts[step.id]
        try:
            args = {k: render_value(v, ctx, keep_unknown=True) for k, v in step.args.items()}
            extra = [soft(a) for a in step.extra_args]
            argv = build_argv(info.command, args, extra)
            verdict = merge_verdicts(verdict, classify_command(info.command, args, extra))
        except ArgvError as err:
            return f"{step.tool} (Argumente noch nicht prüfbar: {err})", verdict
        stdin = None
        if isinstance(step, CommandStep) and step.stdin is not None:
            if step.stdin.pipe is not None:
                stdin = f"pipe: {step.stdin.pipe}"
            else:
                stdin = "text" if step.stdin.text is not None else soft(step.stdin.file or "")
        text = describe(
            argv,
            env={k: soft(v) for k, v in step.env.items() if not env_blocked(k)},
            cwd=soft(step.cwd) if step.cwd else None,
            stdin=stdin,
        )
        return text, verdict

    def block(label: str, steps: Sequence[Step], indent: int) -> None:
        lines.append(PlannedLine(indent, label, "", ""))
        walk(steps, indent + 1)

    def walk(steps: Sequence[Step], indent: int) -> None:
        for step in steps:
            match step:
                case CommandStep() | TerminalStep():
                    text, verdict = command(step)
                    kind = "terminal" if isinstance(step, TerminalStep) else "command"
                    if kind == "terminal":
                        text = f"interaktiv, wird im Trockenlauf übersprungen: {text}"
                    lines.append(
                        PlannedLine(indent, kind, step.id, text, verdict.safety, verdict.reasons)
                    )
                    if step.on_error.steps is not None:
                        block("fallback", step.on_error.steps, indent + 1)
                case IfStep():
                    lines.append(PlannedLine(indent, "if", step.id, _condition(step.condition)))
                    block("then", step.then, indent + 1)
                    if step.else_ is not None:
                        block("else", step.else_, indent + 1)
                case ForeachStep():
                    lines.append(
                        PlannedLine(indent, "foreach", step.id, f"{step.source} als {step.as_}")
                    )
                    block("body", step.body, indent + 1)
                case SetStep():
                    lines.append(
                        PlannedLine(indent, "set", step.id, f"{step.variable} = {soft(step.value)}")
                    )
                case WaitStep():
                    lines.append(PlannedLine(indent, "wait", step.id, f"{step.seconds:g} s"))
                case MessageStep():
                    lines.append(PlannedLine(indent, "message", step.id, soft(step.text)))
                case AbortStep():
                    text = f"{soft(step.text or '')} (exit {step.exit_code})"
                    lines.append(PlannedLine(indent, "abort", step.id, text))

    walk(prepared.workflow.steps, 0)
    return lines


def plan_text(lines: Sequence[PlannedLine]) -> str:
    """Format plan lines as indented text."""
    out: list[str] = []
    for line in lines:
        pad = "  " * line.indent
        if not line.step_id:
            out.append(f"{pad}{line.kind}:")
            continue
        text = f"{pad}{line.step_id} [{line.kind}] {line.text}"
        if line.safety is not None:
            reasons = f": {'; '.join(line.reasons)}" if line.reasons else ""
            text += f"  <{line.safety.value}{reasons}>"
        out.append(text)
    return "\n".join(out)
