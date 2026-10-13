# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run a workflow: prepare (resolve tools, classify, check variables), then execute step by step.

Never uses a shell; commands are argv lists built by `build_argv`. Nothing is executed
in `Runner.prepare`.
"""

import codecs
import dataclasses
import os
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from whattheshell.catalog import Catalog, ToolNotFound
from whattheshell.engine.argv import build_argv, display
from whattheshell.engine.evaluate import EvalError, evaluate
from whattheshell.engine.events import (
    Event,
    Message,
    OutputChunk,
    StepFinished,
    StepSkipped,
    StepStarted,
    WorkflowFinished,
)
from whattheshell.engine.template import (
    Context,
    StepOutput,
    TemplateError,
    render,
    render_value,
    resolve,
)
from whattheshell.models.catalog import ToolInfo
from whattheshell.models.common import Safety, ValueType
from whattheshell.models.workflow import (
    AbortStep,
    CommandStep,
    ForeachStep,
    IfStep,
    MessageStep,
    SetStep,
    Step,
    TerminalStep,
    VariableSpec,
    WaitStep,
    Workflow,
    iter_steps,
)
from whattheshell.paths import inside
from whattheshell.safety import Verdict, classify_command, merge_verdicts, needs_confirmation
from whattheshell.subproc import run_limited

_BLOCKED_ENV = frozenset(
    {
        "PATH",
        "PYTHONPATH",
        "BASH_ENV",
        "ENV",
        "IFS",
        "PROMPT_COMMAND",
        "GCONV_PATH",
        "LOCPATH",
        "NODE_OPTIONS",
        "PERL5OPT",
        "PERL5LIB",
        "RUBYOPT",
        "PYTHONSTARTUP",
        "PYTHONHOME",
        "GIT_SSH_COMMAND",
        "GIT_EXEC_PATH",
        "LESSOPEN",
        "PAGER",
        "MANPAGER",
        "EDITOR",
        "BROWSER",
    }
)
_BLOCKED_ENV_PREFIXES = ("LD_", "GIT_CONFIG")
_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_TIMEOUT = 86400.0
_POLL = 0.1
TERMINAL_ONLY_GUI = "Terminal-Schritte laufen nur in `wts gui`. Workflow dort starten."


class RunError(Exception):
    """The workflow cannot be started; nothing has been executed."""


@dataclass
class StepResult:
    """Recorded outcome of the last attempt of a command step (texts masked)."""

    step_id: str
    argv: list[str]
    command: str
    started: datetime
    finished: datetime
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool
    ok: bool
    attempts: int


@dataclass
class RunResult:
    """Outcome of a whole run; variables of type secret are masked."""

    status: Literal["success", "failed", "aborted"]
    message: str
    exit_code: int
    results: dict[str, StepResult]
    variables: dict[str, str]


@dataclass(frozen=True)
class ConfirmRequest:
    """Question to the user before a caution or dangerous step runs."""

    step_id: str
    command: str
    safety: Safety
    reasons: tuple[str, ...]


Confirmer = Callable[[ConfirmRequest], bool]


@dataclass(frozen=True)
class TerminalRequest:
    """Interactive process the provider must run; `abort` is set when the run is cancelled."""

    step_id: str
    argv: list[str]
    env: dict[str, str]  # only the step's own env (blocklist applied), never os.environ
    cwd: Path
    command: str  # display text, secrets masked
    secrets: tuple[str, ...]  # run-time secret values, for masking transcripts
    timeout: float
    network: bool
    safety: Safety
    reasons: tuple[str, ...]
    abort: threading.Event


# Blocks the runner thread until the process ends; returns its exit code.
TerminalProvider = Callable[[TerminalRequest], int]


@dataclass
class Controller:
    """Run control by the caller; the runner only waits on these events."""

    abort: threading.Event = field(default_factory=threading.Event)
    pause: threading.Event = field(default_factory=threading.Event)
    step_release: threading.Event = field(default_factory=threading.Event)
    step_mode: bool = False


@dataclass
class Prepared:
    """A workflow with checked variables, resolved tools and safety verdicts."""

    workflow: Workflow
    variables: dict[str, str]
    specs: dict[str, ToolInfo]
    verdicts: dict[str, Verdict]
    root: Path


def _text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _check_type(name: str, spec: VariableSpec, value: str) -> None:
    kind = spec.type
    try:
        number = float(value) if kind in (ValueType.int, ValueType.float) else None
        if kind is ValueType.int:
            int(value)
        elif kind is ValueType.bool and value not in ("true", "false"):
            raise ValueError
    except ValueError:
        hint = " (true oder false)" if kind is ValueType.bool else ""
        raise RunError(
            f"Variable '{name}': Wert passt nicht zu Typ {kind.value}{hint}. Wert korrigieren."
        ) from None
    if kind is ValueType.enum and spec.choices and value not in spec.choices:
        raise RunError(
            f"Variable '{name}': '{value}' ist keine erlaubte Auswahl "
            f"({', '.join(spec.choices)}). Einen dieser Werte angeben."
        )
    if number is not None:
        if spec.min is not None and number < spec.min:
            raise RunError(f"Variable '{name}': {value} ist kleiner als das Minimum {spec.min:g}.")
        if spec.max is not None and number > spec.max:
            raise RunError(f"Variable '{name}': {value} ist größer als das Maximum {spec.max:g}.")


def env_blocked(key: str) -> bool:
    """True for environment keys a step must not set (code-loading or malformed names)."""
    return key.startswith(_BLOCKED_ENV_PREFIXES) or key in _BLOCKED_ENV or not _ENV_KEY.match(key)


def extra_risks(
    *,
    has_env: bool,
    cwd: Path | None,
    stdin_file: Path | None,
    root: Path,
    terminal: TerminalStep | None = None,
) -> Verdict:
    """Caution for environment changes, paths outside the workflow folder, terminal steps."""
    reasons: list[str] = []
    if terminal is not None:
        reasons.append("interaktiv")
        if terminal.network:
            reasons.append("Netzzugang")
    if has_env:
        reasons.append("setzt Umgebungsvariablen")
    if cwd is not None and not inside(cwd, root):
        reasons.append("Arbeitsverzeichnis außerhalb des Workflow-Ordners")
    if stdin_file is not None and not inside(stdin_file, root):
        reasons.append("liest Datei außerhalb")
    return Verdict(Safety.caution if reasons else Safety.safe, tuple(reasons))


def _terminal_cwd_error(cwd: Path, root: Path) -> str | None:
    if inside(cwd, root):
        return None
    return f"Terminal-Schritt: cwd muss innerhalb von {root} liegen (ist: {cwd.resolve()})"


def _static_path(text: str | None, variables: Mapping[str, str], root: Path) -> Path | None:
    """Path from a template as far as renderable now; None if empty or still unresolved."""
    if not text:
        return None
    rendered = render(text, Context(variables, {}), keep_unknown=True)
    return None if "{{" in rendered or "\x00" in rendered else root / rendered


def describe(
    argv: Sequence[str], *, env: Mapping[str, str], cwd: str | None, stdin: str | None
) -> str:
    """Display text of a command with its environment, directory and stdin (display only)."""
    head = ["env", *(f"{key}={value}" for key, value in env.items())] if env else []
    text = display([*head, *argv])
    if cwd:
        text += f" (in {cwd})"
    if stdin:
        text += f" < {stdin}"
    return text


def secret_values(workflow: Workflow, variables: Mapping[str, str]) -> list[str]:
    """Non-empty values of secret variables, longest first."""
    values = {
        variables[name]
        for name, spec in workflow.variables.items()
        if spec.type is ValueType.secret and variables.get(name)
    }
    return sorted(values, key=len, reverse=True)


def mask_text(text: str, secrets: Sequence[str]) -> str:
    """Replace every secret value in `text` by ``***``."""
    for secret in secrets:
        text = text.replace(secret, "***")
    return text


class _LineEmitter:
    """Turn raw chunks into complete decoded lines; the rest is emitted by `flush`.

    Lines, not chunks, are masked so a secret split across two reads does not leak.
    """

    def __init__(self, emit: Callable[[Literal["stdout", "stderr"], str], None]) -> None:
        self._emit = emit
        self._decoders = {
            s: codecs.getincrementaldecoder("utf-8")(errors="replace") for s in ("stdout", "stderr")
        }
        self._buffers = {"stdout": "", "stderr": ""}

    def feed(self, stream: str, data: bytes) -> None:
        buffer = self._buffers[stream] + self._decoders[stream].decode(data)
        head, newline, tail = buffer.rpartition("\n")
        self._buffers[stream] = tail
        if newline:
            self._emit(stream, head + newline)  # type: ignore[arg-type]

    def flush(self) -> None:
        for stream in ("stdout", "stderr"):
            rest = self._buffers[stream] + self._decoders[stream].decode(b"", final=True)
            self._buffers[stream] = ""
            if rest:
                self._emit(stream, rest)


@dataclass
class _Built:
    argv: list[str]
    command: str
    env: dict[str, str]
    cwd: Path
    stdin: bytes | None
    verdict: Verdict


class _StepError(Exception):
    """A step cannot be run as configured (message is shown to the user)."""


class Runner:
    """Executes a prepared workflow; one run at a time per instance."""

    def __init__(
        self,
        catalog: Catalog,
        *,
        confirm: Confirmer,
        on_event: Callable[[Event], None] | None = None,
        controller: Controller | None = None,
        cwd: Path,
        output_limit: int = 1_048_576,
        step_timeout: float | None = None,
        terminal: TerminalProvider | None = None,
    ) -> None:
        self._catalog = catalog
        self._confirm = confirm
        self._on_event = on_event
        self._controller = controller or Controller()
        self._cwd = Path(cwd).resolve()
        self._output_limit = output_limit
        self._step_timeout = step_timeout
        self._terminal = terminal

    def prepare(self, workflow: Workflow, overrides: Mapping[str, str]) -> Prepared:
        """Check variables, resolve every tool and classify every command; runs nothing.

        Raises:
            RunError: Unknown or ill-typed variable, missing required value, unknown tool.
        """
        unknown = sorted(set(overrides) - set(workflow.variables))
        if unknown:
            raise RunError(
                f"Unbekannte Variable(n): {', '.join(unknown)}. "
                f"Deklariert: {', '.join(workflow.variables) or 'keine'}."
            )
        variables: dict[str, str] = {}
        for name, spec in workflow.variables.items():
            if name in overrides:
                variables[name] = overrides[name]
            elif spec.default is not None:
                variables[name] = _text(spec.default)
            elif spec.required:
                raise RunError(
                    f"Pflichtvariable '{name}' hat keinen Wert. Mit --var {name}=WERT angeben."
                )
            else:
                continue
            _check_type(name, spec, variables[name])
        specs: dict[str, ToolInfo] = {}
        verdicts: dict[str, Verdict] = {}
        for step in iter_steps(workflow.steps):
            if not isinstance(step, CommandStep | TerminalStep):
                continue
            try:
                info = self._catalog.get(step.tool, step.command)
            except ToolNotFound as err:
                raise RunError(f"Schritt '{step.id}': {err}") from err
            except (OSError, ValidationError) as err:
                raise RunError(
                    f"Schritt '{step.id}': Tool '{step.tool}' konnte nicht gelesen werden: {err}"
                ) from err
            specs[step.id] = info
            static_cwd = _static_path(step.cwd, variables, self._cwd)
            if (
                isinstance(step, TerminalStep)
                and static_cwd is not None
                and (message := _terminal_cwd_error(static_cwd, self._cwd))
            ):
                raise RunError(f"Schritt '{step.id}': {message}")
            verdicts[step.id] = merge_verdicts(
                classify_command(info.command, step.args, step.extra_args),
                extra_risks(
                    has_env=bool(step.env),
                    cwd=static_cwd,
                    stdin_file=_static_path(
                        step.stdin.file if isinstance(step, CommandStep) and step.stdin else None,
                        variables,
                        self._cwd,
                    ),
                    root=self._cwd,
                    terminal=step if isinstance(step, TerminalStep) else None,
                ),
            )
        return Prepared(workflow, variables, specs, verdicts, self._cwd)

    # ------------------------------------------------------------------ run

    def run(self, prepared: Prepared) -> RunResult:
        """Execute the workflow; the last event is always `WorkflowFinished`."""
        self._prepared = prepared
        self._variables = dict(prepared.variables)
        self._outputs: dict[str, StepOutput] = {}
        self._stdout_bytes: dict[str, bytes] = {}
        self._results: dict[str, StepResult] = {}
        self._final: tuple[Literal["success", "failed", "aborted"], str, int] | None = None
        ctx = Context(self._variables, self._outputs)
        if self._terminal is None and any(
            isinstance(step, TerminalStep) for step in iter_steps(prepared.workflow.steps)
        ):
            self._finish("failed", TERMINAL_ONLY_GUI, 3)  # before any process starts
        elif self._steps(prepared.workflow.steps, ctx):
            self._finish("success", "Workflow abgeschlossen", 0)
        assert self._final is not None  # noqa: S101
        status, message, exit_code = self._final
        message = self._mask(message)
        self._emit(WorkflowFinished(status, message))
        secrets = secret_values(prepared.workflow, self._variables)
        return RunResult(
            status,
            message,
            exit_code,
            self._results,
            {k: mask_text(v, secrets) for k, v in self._variables.items()},
        )

    def _emit(self, event: Event) -> None:
        """Single exit for events: every text field is masked here."""
        if self._on_event is None:
            return
        mask = self._mask
        match event:
            case StepStarted():
                event = dataclasses.replace(event, command=mask(event.command))
            case OutputChunk() | Message():
                event = dataclasses.replace(event, text=mask(event.text))
            case WorkflowFinished():
                event = dataclasses.replace(event, message=mask(event.message))
            case StepSkipped():
                event = dataclasses.replace(event, reason=mask(event.reason))
            case _:
                pass
        self._on_event(event)

    def _mask(self, text: str) -> str:
        return mask_text(text, secret_values(self._prepared.workflow, self._variables))

    def _finish(
        self, status: Literal["success", "failed", "aborted"], message: str, code: int
    ) -> None:
        if self._final is None:
            self._final = (status, message, code)

    def _gate(self) -> bool:
        """Wait for step release and pause; False if the run was aborted."""
        control = self._controller
        if control.step_mode:
            while not control.step_release.wait(_POLL):
                if control.abort.is_set():
                    return False
            control.step_release.clear()
        while control.pause.is_set() and not control.abort.is_set():
            control.abort.wait(_POLL)
        return not control.abort.is_set()

    def _steps(self, steps: Sequence[Step], ctx: Context) -> bool:
        """Run steps in order; False once the workflow has ended."""
        for step in steps:
            if not self._gate():
                self._finish("aborted", "Abgebrochen", 2)
                return False
            if not self._step(step, ctx):
                return False
        return True

    def _skip(self, steps: Sequence[Step], reason: str) -> None:
        for step in steps:
            self._emit(StepSkipped(step.id, reason))

    def _step(self, step: Step, ctx: Context) -> bool:
        match step:
            case CommandStep() | TerminalStep():
                return self._command(step, ctx)
            case IfStep():
                try:
                    taken = evaluate(step.condition, ctx, cwd=self._cwd)
                except EvalError as err:
                    self._finish("failed", f"Schritt '{step.id}': Bedingung: {err}", 1)
                    return False
                chosen, other = (
                    (step.then, step.else_ or []) if taken else (step.else_ or [], step.then)
                )
                self._skip(other, f"Bedingung von '{step.id}' wählt {'then' if taken else 'else'}")
                return self._steps(chosen, ctx)
            case ForeachStep():
                try:
                    source = resolve(step.source, ctx)
                except TemplateError as err:
                    self._finish("failed", f"Schritt '{step.id}': Quelle: {err}", 1)
                    return False
                items = [line.rstrip() for line in source.splitlines() if line.strip()]
                if not items:
                    self._skip(step.body, f"Quelle von '{step.id}' ist leer")
                for item in items:
                    inner = Context(
                        ctx.variables,
                        ctx.results,
                        {**ctx.items, step.as_: item, "item": item},
                    )
                    if not self._steps(step.body, inner):
                        return False
                return True
            case SetStep():
                value = self._try_render(step, step.value, ctx)
                if value is not None:
                    self._variables[step.variable] = value
                return value is not None
            case WaitStep():
                deadline = time.monotonic() + step.seconds
                while (left := deadline - time.monotonic()) > 0:
                    if self._controller.abort.wait(min(_POLL, left)):
                        self._finish("aborted", "Abgebrochen", 2)
                        return False
                return True
            case MessageStep():
                text = self._try_render(step, step.text, ctx)
                if text is not None:
                    self._emit(Message(step.id, text))
                return text is not None
            case AbortStep():
                text = self._try_render(step, step.text or "", ctx)
                if text is not None:
                    self._finish("aborted", text or "Workflow abgebrochen", step.exit_code)
                return False

    def _try_render(self, step: Step, text: str, ctx: Context) -> str | None:
        try:
            return render(text, ctx)
        except TemplateError as err:
            self._finish("failed", f"Schritt '{step.id}': {err}", 1)
            return None

    # -------------------------------------------------------------- command

    def _build(self, step: CommandStep | TerminalStep, ctx: Context) -> _Built:
        """Render and assemble everything for one run; the class is recomputed from real values."""
        info = self._prepared.specs[step.id]
        try:
            args = {k: render_value(v, ctx) for k, v in step.args.items()}
            extra = [render(a, ctx) for a in step.extra_args]
            argv = build_argv(info.command, args, extra, tool_path=info.path)
            # terminal steps get only their own env; the sandbox supplies the base
            env = {} if isinstance(step, TerminalStep) else dict(os.environ)
            added: dict[str, str] = {}
            for key, value in step.env.items():
                if env_blocked(key):
                    self._emit(
                        Message(
                            step.id, f"WARNUNG: Umgebungsvariable '{key}' nicht erlaubt, verworfen"
                        )
                    )
                else:
                    added[key] = env[key] = render(value, ctx)
            cwd = self._cwd
            if step.cwd:
                cwd = (self._cwd / render(step.cwd, ctx)).resolve()
            if isinstance(step, TerminalStep) and (message := _terminal_cwd_error(cwd, self._cwd)):
                raise _StepError(message)
            if not cwd.is_dir():
                raise _StepError(f"Arbeitsverzeichnis '{cwd}' existiert nicht")
            stdin, stdin_file, stdin_label = (
                self._stdin(step, ctx, cwd) if isinstance(step, CommandStep) else (None, None, None)
            )
        except (TemplateError, OSError, ValueError) as err:  # ArgvError is a ValueError
            raise _StepError(str(err)) from err
        verdict = merge_verdicts(
            merge_verdicts(
                self._prepared.verdicts[step.id], classify_command(info.command, args, extra)
            ),
            extra_risks(
                has_env=bool(step.env),
                cwd=cwd if step.cwd else None,
                stdin_file=stdin_file,
                root=self._cwd,
                terminal=step if isinstance(step, TerminalStep) else None,
            ),
        )
        shown = describe(
            [self._mask(a) for a in (info.command.name[0], *argv[1:])],
            env={k: self._mask(v) for k, v in added.items()},
            cwd=self._mask(str(cwd)) if step.cwd else None,
            stdin=self._mask(stdin_label) if stdin_label else None,
        )
        return _Built(argv, shown, env, cwd, stdin, verdict)

    def _stdin(
        self, step: CommandStep, ctx: Context, cwd: Path
    ) -> tuple[bytes | None, Path | None, str | None]:
        """Returns the bytes, the file read (if any) and a display label."""
        if step.stdin is None:
            return None, None, None
        if step.stdin.pipe is not None:
            if step.stdin.pipe not in self._stdout_bytes:
                raise _StepError(
                    f"stdin.pipe '{step.stdin.pipe}': Schritt hat keine Ausgabe (nicht gelaufen?)"
                )
            return self._stdout_bytes[step.stdin.pipe], None, f"pipe: {step.stdin.pipe}"
        if step.stdin.text is not None:
            return render(step.stdin.text, ctx).encode(), None, "text"
        assert step.stdin.file is not None  # noqa: S101
        path = (cwd / render(step.stdin.file, ctx)).resolve()
        try:
            return path.read_bytes(), path, str(path)
        except (OSError, ValueError) as err:
            raise _StepError(f"stdin.file '{path}' nicht lesbar: {err}") from err

    def _command(self, step: CommandStep | TerminalStep, ctx: Context) -> bool:
        try:
            built = self._build(step, ctx)
        except _StepError as err:
            self._emit(StepStarted(step.id, step.tool, self._prepared.verdicts[step.id].safety))
            self._record(
                step,
                [],
                step.tool,
                datetime.now().astimezone(),
                None,
                str(err),
                b"",
                b"",
                False,
                False,
                1,
            )
            self._emit(StepFinished(step.id, None, False, 0.0, 1))
            return self._failed(step, ctx, str(err))
        verdict = built.verdict
        if needs_confirmation(verdict.safety) and not self._confirm(
            ConfirmRequest(step.id, built.command, verdict.safety, verdict.reasons)
        ):
            self._finish("aborted", f"Schritt '{step.id}' vom Nutzer abgelehnt", 2)
            return False
        self._emit(StepStarted(step.id, built.command, verdict.safety))
        attempts = 1 + (step.on_error.retries or 0)
        for attempt in range(1, attempts + 1):
            if isinstance(step, TerminalStep):
                ok, reason = self._run_terminal(step, built, attempt)
            else:
                ok, reason = self._execute(step, built, attempt)
            if ok:
                return True
            if self._controller.abort.is_set():
                self._finish("aborted", "Abgebrochen", 2)
                return False
        return self._failed(step, ctx, reason)

    def _failed(self, step: CommandStep | TerminalStep, ctx: Context, reason: str) -> bool:
        """Apply `on_error` after the final failed attempt; True means the run goes on."""
        action = step.on_error.action
        if action == "continue":
            self._emit(Message(step.id, f"Schritt '{step.id}' fehlgeschlagen ({reason}), weiter"))
            return True
        if action == "fallback":
            self._emit(
                Message(step.id, f"Schritt '{step.id}' fehlgeschlagen ({reason}), Ersatzschritte")
            )
            return self._steps(step.on_error.steps or [], ctx)
        self._finish("failed", f"Schritt '{step.id}' fehlgeschlagen: {reason}", 1)
        return False

    def _execute(self, step: CommandStep, built: _Built, attempt: int) -> tuple[bool, str]:
        """Run one attempt, record and report it; returns (ok, failure reason)."""
        emitter = _LineEmitter(lambda s, t: self._emit(OutputChunk(step.id, s, t)))
        started = datetime.now().astimezone()
        clock = time.monotonic()
        raw = None
        error = None
        try:
            raw = run_limited(
                built.argv,
                timeout=step.timeout or self._step_timeout or _MAX_TIMEOUT,
                max_bytes=self._output_limit,
                env=built.env,
                cwd=str(built.cwd),
                stdin=built.stdin,
                on_chunk=emitter.feed,
                cancel=self._controller.abort,
            )
            if raw is None:
                error = (
                    f"Programm '{built.argv[0]}' konnte nicht gestartet werden (Rechte, Format?)"
                )
        except ValueError as err:  # NUL byte in argv or environment
            error = f"Ungültiges Argument oder Umgebung: {err}"
        emitter.flush()
        if raw is None:
            reason = error or ""
            self._record(
                step,
                built.argv,
                built.command,
                started,
                None,
                reason,
                b"",
                b"",
                False,
                False,
                attempt,
            )
            self._emit(StepFinished(step.id, None, False, time.monotonic() - clock, attempt))
            return False, reason
        ok = raw.exit_code in step.ok_exit_codes and not (
            raw.timed_out or raw.truncated or raw.cancelled
        )
        self._record(
            step,
            built.argv,
            built.command,
            started,
            raw.exit_code,
            None,
            raw.stdout,
            raw.stderr,
            raw.truncated,
            ok,
            attempt,
        )
        self._emit(StepFinished(step.id, raw.exit_code, ok, time.monotonic() - clock, attempt))
        if raw.timed_out:
            return ok, "Zeitlimit überschritten"
        if raw.truncated:
            return ok, f"Ausgabelimit von {self._output_limit} Bytes überschritten"
        if raw.cancelled:
            return ok, "Abgebrochen"
        return ok, f"Exit-Code {raw.exit_code}, erlaubt: {step.ok_exit_codes}"

    def _run_terminal(self, step: TerminalStep, built: _Built, attempt: int) -> tuple[bool, str]:
        """One interactive attempt; later steps get no output (empty stdout/stderr)."""
        assert self._terminal is not None  # noqa: S101 (checked at the start of `run`)
        started = datetime.now().astimezone()
        clock = time.monotonic()
        request = TerminalRequest(
            step.id,
            built.argv,
            built.env,
            built.cwd,
            built.command,
            tuple(secret_values(self._prepared.workflow, self._variables)),
            step.timeout or self._step_timeout or _MAX_TIMEOUT,
            step.network,
            built.verdict.safety,
            built.verdict.reasons,
            self._controller.abort,
        )
        code: int | None = None
        error = None
        try:
            code = self._terminal(request)
        except OSError as err:
            error = f"Terminal konnte nicht gestartet werden: {err}"
        ok = code in step.ok_exit_codes and not self._controller.abort.is_set()
        self._record(
            step, built.argv, built.command, started, code, error, b"", b"", False, ok, attempt
        )
        self._emit(StepFinished(step.id, code, ok, time.monotonic() - clock, attempt))
        if error:
            return False, error
        if self._controller.abort.is_set():
            return False, "Abgebrochen"
        return ok, f"Exit-Code {code}, erlaubt: {step.ok_exit_codes}"

    def _record(
        self,
        step: CommandStep | TerminalStep,
        argv: list[str],
        command: str,
        started: datetime,
        exit_code: int | None,
        error: str | None,
        stdout: bytes,
        stderr: bytes,
        truncated: bool,
        ok: bool,
        attempt: int,
    ) -> None:
        """Store the attempt: raw text for templates and pipes, masked text in the result."""
        out = stdout.decode("utf-8", errors="replace")
        err = error if error is not None else stderr.decode("utf-8", errors="replace")
        self._outputs[step.id] = StepOutput(out, err, -1 if exit_code is None else exit_code)
        self._stdout_bytes[step.id] = stdout
        self._results[step.id] = StepResult(
            step.id,
            [self._mask(a) for a in argv],
            command,
            started,
            datetime.now().astimezone(),
            exit_code,
            self._mask(out),
            self._mask(err),
            truncated,
            ok,
            attempt,
        )
