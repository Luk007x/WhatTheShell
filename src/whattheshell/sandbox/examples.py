# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run module examples inside the sandbox and check their ``expect`` block."""

import logging
import re
import shlex
import tempfile
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from whattheshell.catalog.catalog import Catalog, ToolNotFound
from whattheshell.engine.argv import ArgvError, build_argv
from whattheshell.models.catalog import ToolInfo
from whattheshell.models.module import Example
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.paths import inside
from whattheshell.sandbox import SandboxStatus, run_sandboxed

logger = logging.getLogger(__name__)
_SHOWN = 200


@dataclass(frozen=True)
class ExampleResult:
    """Outcome of one example; empty ``failures`` and no ``skipped`` means passed."""

    tool: str
    title: str
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration: float
    failures: tuple[str, ...]
    skipped: str | None


def _cut(text: str) -> str:
    return text if len(text) <= _SHOWN else text[:_SHOWN] + "…"


def _write_fixtures(example: Example, workdir: Path) -> list[str]:
    root = workdir.resolve()
    failures: list[str] = []
    for fixture in example.fixtures:
        target = root / fixture.path
        if not inside(target, root):
            failures.append(
                f"Fixture-Pfad {fixture.path!r} liegt außerhalb des Arbeitsverzeichnisses"
            )
            continue
        target = target.resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(fixture.content, encoding="utf-8")
        except OSError as err:
            failures.append(f"Fixture {fixture.path!r} nicht schreibbar: {err}")
    return failures


def _check(example: Example, exit_code: int, stdout: str, stderr: str) -> list[str]:
    expect = example.expect
    if expect is None:
        return []
    failures: list[str] = []
    if expect.exit_code is not None and expect.exit_code != exit_code:
        failures.append(f"Exit-Code: erwartet {expect.exit_code}, ist {exit_code}")
    if expect.stdout_contains is not None and expect.stdout_contains not in stdout:
        failures.append(f"stdout enthält nicht {expect.stdout_contains!r}; ist: {_cut(stdout)!r}")
    if expect.stderr_contains is not None and expect.stderr_contains not in stderr:
        failures.append(f"stderr enthält nicht {expect.stderr_contains!r}; ist: {_cut(stderr)!r}")
    if expect.stdout_regex is not None and not re.search(expect.stdout_regex, stdout):
        failures.append(f"stdout passt nicht auf /{expect.stdout_regex}/; ist: {_cut(stdout)!r}")
    return failures


def run_example(
    info: ToolInfo, example: Example, *, status: SandboxStatus, timeout: float = 10.0
) -> ExampleResult:
    """Run one example in a fresh sandbox workdir and compare with its ``expect``."""

    def result(
        command: str = "",
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
        duration: float = 0.0,
        failures: Sequence[str] = (),
        skipped: str | None = None,
    ) -> ExampleResult:
        return ExampleResult(
            info.name, example.title, command, exit_code, stdout, stderr, duration,
            tuple(failures), skipped,
        )  # fmt: skip

    if not status.available:
        return result(skipped=status.reason)
    with tempfile.TemporaryDirectory(prefix="wts-example-") as tmp:
        workdir = Path(tmp)
        workdir.chmod(0o700)
        if failures := _write_fixtures(example, workdir):
            return result(failures=failures)
        try:
            argv = build_argv(info.command, example.args, tool_path=info.path)
        except ArgvError as err:
            return result(failures=[f"Argumente: {err}"])
        command = shlex.join(argv)
        start = time.monotonic()
        done = run_sandboxed(argv, workdir, timeout=timeout)
        duration = time.monotonic() - start
    if done is None:
        return result(command, duration=duration, failures=["Sandbox konnte nicht starten"])
    stdout = done.stdout.decode(errors="replace")
    stderr = done.stderr.decode(errors="replace")
    failures = _check(example, done.exit_code, stdout, stderr)
    if done.truncated:
        failures.append("Ausgabe über dem Limit abgeschnitten")
    if done.timed_out:
        failures.append(f"Zeitüberschreitung nach {timeout:g} s")
    return result(command, done.exit_code, stdout, stderr, duration, failures)


def iter_examples(
    catalog: Catalog, registry: ModuleRegistry, tools: Sequence[str] | None = None
) -> Iterator[tuple[ToolInfo, Example]]:
    """Yield every example of the registry's tools; tools missing on PATH are skipped."""
    names = dict.fromkeys(loaded.module.tool for loaded in registry.all())
    for name in names:
        if tools is not None and name not in tools:
            continue
        try:
            info = catalog.get(name)
        except ToolNotFound:
            logger.info("Tool %s nicht installiert, Beispiele übersprungen", name)
            continue
        for example in info.command.examples:
            yield info, example
