# SPDX-License-Identifier: AGPL-3.0-or-later
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from whattheshell.bundled import MODULES_DIR, WORKFLOWS_DIR
from whattheshell.catalog import Catalog
from whattheshell.engine import (
    ConfirmRequest,
    Controller,
    Event,
    Message,
    OutputChunk,
    RunError,
    Runner,
    RunResult,
    StepSkipped,
    StepStarted,
    WorkflowFinished,
)
from whattheshell.models.workflow import Workflow
from whattheshell.modules.loader import load_workflow_file
from whattheshell.modules.registry import ModuleRegistry

# Every script answers --help/--version itself, so catalog probing never runs the body.
_PREAMBLE = """#!/bin/sh
case "$1" in
  --help)
    printf 'Usage: %s [OPTION]... [ARG]...\\n\\nTest tool.\\n\\n' "${0##*/}"
    printf 'Options:\\n  -v, --verbose  verbose\\n'
    exit 0;;
  --version) echo "1.0"; exit 0;;
esac
"""


def _tools(bin_dir: Path, counter: Path) -> dict[str, str]:
    return {
        "echo-args": 'for a in "$@"; do printf \'%s\\n\' "$a"; done',
        "fail": "exit 3",
        "failerr": "echo boom >&2; exit 3",
        "mycat": "cat",
        "env-dump": 'if printenv "$1"; then :; else echo UNSET; fi',
        "napper": "sleep 5",
        # caution tool by name; records every real invocation
        "git": f'echo run >> "{counter}"',
        "find": f'echo run >> "{counter}"',
        # succeeds from the third call on
        "flaky": (
            f'n=$(cat "{counter}.flaky" 2>/dev/null || echo 0); n=$((n+1)); '
            f'echo $n > "{counter}.flaky"; [ $n -ge 3 ]'
        ),
    }


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put test scripts first on PATH; returns the counter file used by `git`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    counter = tmp_path / "counter"
    for name, body in _tools(bin_dir, counter).items():
        path = bin_dir / name
        path.write_text(_PREAMBLE + body + "\n")
        path.chmod(0o755)
    monkeypatch.setenv(
        "PATH",
        f"{bin_dir}:{shutil.which('sh') and Path(shutil.which('sh') or '').parent}:/usr/bin:/bin",
    )
    return counter


def make_workflow(steps: list[dict[str, Any]], variables: dict[str, Any] | None = None) -> Workflow:
    return Workflow.model_validate(
        {"schema_version": 1, "name": "t", "variables": variables or {}, "steps": steps}
    )


def make_runner(
    tmp_path: Path,
    *,
    confirm: Callable[[ConfirmRequest], bool] = lambda request: True,
    controller: Controller | None = None,
    **kwargs: Any,
) -> tuple[Runner, list[Event]]:
    events: list[Event] = []
    runner = Runner(
        Catalog(cache_dir=tmp_path / "cache"),
        confirm=confirm,
        on_event=events.append,
        controller=controller,
        cwd=tmp_path,
        **kwargs,
    )
    return runner, events


def run(
    tmp_path: Path,
    workflow: Workflow,
    overrides: dict[str, str] | None = None,
    **kwargs: Any,
) -> tuple[RunResult, list[Event]]:
    runner, events = make_runner(tmp_path, **kwargs)
    return runner.run(runner.prepare(workflow, overrides or {})), events


def echo(step_id: str, *words: str, **extra: Any) -> dict[str, Any]:
    return {"id": step_id, "tool": "echo-args", "extra_args": list(words), **extra}


pytestmark = pytest.mark.usefixtures("tools")


def test_pipe_feeds_stdout_into_stdin(tmp_path: Path) -> None:
    wf = make_workflow([echo("a", "x", "y"), {"id": "b", "tool": "mycat", "stdin": {"pipe": "a"}}])
    result, events = run(tmp_path, wf)
    assert result.status == "success" and result.exit_code == 0
    assert list(result.results) == ["a", "b"]
    assert result.results["b"].stdout == "x\ny\n"
    assert [e.text for e in events if isinstance(e, OutputChunk) and e.step_id == "b"] == ["x\ny\n"]
    assert isinstance(events[-1], WorkflowFinished) and events[-1].status == "success"


def test_variables_override_and_errors(tmp_path: Path) -> None:
    wf = make_workflow(
        [echo("a", "{{ var.n }}")],
        {"n": {"type": "int", "default": 1}, "must": {"required": True}},
    )
    runner, _ = make_runner(tmp_path)
    with pytest.raises(RunError, match="must"):
        runner.prepare(wf, {})
    with pytest.raises(RunError, match="Typ int"):
        runner.prepare(wf, {"must": "x", "n": "abc"})
    with pytest.raises(RunError, match="Unbekannte Variable.*other"):
        runner.prepare(wf, {"must": "x", "other": "1"})
    result = runner.run(runner.prepare(wf, {"must": "x", "n": "42"}))
    assert result.results["a"].stdout == "42\n"
    assert result.variables == {"n": "42", "must": "x"}


def test_unknown_tool_fails_in_prepare_before_any_step(tmp_path: Path, tools: Path) -> None:
    wf = make_workflow([{"id": "a", "tool": "git"}, {"id": "b", "tool": "no-such-tool-wts"}])
    runner, events = make_runner(tmp_path)
    with pytest.raises(RunError, match="Schritt 'b'.*nicht auf PATH"):
        runner.prepare(wf, {})
    assert events == [] and not tools.exists()


@pytest.mark.parametrize(("lines", "branch"), [(["a", "b", "c"], "then"), (["a"], "else")])
def test_if_number_and_lines(tmp_path: Path, lines: list[str], branch: str) -> None:
    wf = make_workflow(
        [
            echo("src", *lines),
            {
                "id": "chk",
                "kind": "if",
                "condition": {"source": "src.stdout", "line_count_gt": 1},
                "then": [echo("t", "then")],
                "else": [echo("e", "else")],
            },
        ]
    )
    result, events = run(tmp_path, wf)
    assert list(result.results) == ["src", "t" if branch == "then" else "e"]
    skipped = [e for e in events if isinstance(e, StepSkipped)]
    assert [s.step_id for s in skipped] == ["e" if branch == "then" else "t"]


def test_foreach_with_item_and_as(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            echo("src", "one", "", "two  ", "three"),
            {
                "id": "loop",
                "kind": "foreach",
                "source": "src.stdout",
                "as": "datei",
                "body": [echo("each", "[{{ datei }}]", "{{ item }}")],
            },
        ]
    )
    result, events = run(tmp_path, wf)
    started = [e for e in events if isinstance(e, StepStarted) and e.step_id == "each"]
    assert len(started) == 3  # empty line skipped
    assert result.results["each"].stdout == "[three]\nthree\n"


def test_set_then_template(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            echo("a", "hello"),
            {"id": "s", "kind": "set", "variable": "x", "value": "<{{ a.stdout }}>"},
            echo("b", "{{ var.x }}"),
        ],
        {"x": {}},
    )
    result, _ = run(tmp_path, wf)
    assert result.variables["x"] == "<hello\n>"
    assert result.results["b"].stdout == "<hello\n>\n"


def test_on_error_continue(tmp_path: Path) -> None:
    wf = make_workflow(
        [{"id": "f", "tool": "fail", "on_error": {"action": "continue"}}, echo("after", "ok")]
    )
    result, events = run(tmp_path, wf)
    assert result.status == "success" and not result.results["f"].ok
    assert result.results["f"].exit_code == 3 and "after" in result.results
    assert any(isinstance(e, Message) and "fehlgeschlagen" in e.text for e in events)


def test_on_error_retry(tmp_path: Path) -> None:
    ok = make_workflow(
        [{"id": "f", "tool": "flaky", "on_error": {"action": "retry", "retries": 2}}]
    )
    result, _ = run(tmp_path, ok)
    assert result.status == "success" and result.results["f"].attempts == 3
    (tmp_path / "counter.flaky").unlink()
    short = make_workflow(
        [{"id": "f", "tool": "flaky", "on_error": {"action": "retry", "retries": 1}}]
    )
    result, _ = run(tmp_path, short)
    assert result.status == "failed" and result.results["f"].attempts == 2


def test_on_error_fallback_sees_failed_step(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            {
                "id": "x",
                "tool": "failerr",
                "on_error": {"action": "fallback", "steps": [echo("fb", "got:{{ x.stderr }}")]},
            },
            echo("next", "n"),
        ]
    )
    result, _ = run(tmp_path, wf)
    assert result.status == "success"
    assert "got:boom" in result.results["fb"].stdout and "next" in result.results


def test_nested_foreach_sees_both_names(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            echo("outer_src", "a", "b"),
            {
                "id": "o",
                "kind": "foreach",
                "source": "outer_src.stdout",
                "as": "x",
                "body": [
                    {
                        "id": "i",
                        "kind": "foreach",
                        "source": "outer_src.stdout",
                        "as": "y",
                        "body": [echo("e", "{{ x }}{{ y }}{{ item }}")],
                    }
                ],
            },
        ]
    )
    result, events = run(tmp_path, wf)
    started = [e for e in events if isinstance(e, StepStarted) and e.step_id == "e"]
    assert [e.command for e in started] == [
        "echo-args aaa",
        "echo-args abb",
        "echo-args baa",
        "echo-args bbb",
    ]


def test_on_error_abort_stops(tmp_path: Path) -> None:
    wf = make_workflow([{"id": "f", "tool": "fail"}, echo("never", "x")])
    result, events = run(tmp_path, wf)
    assert result.status == "failed" and "never" not in result.results
    assert "Exit-Code 3" in result.message
    assert isinstance(events[-1], WorkflowFinished) and events[-1].status == "failed"


def test_ok_exit_codes(tmp_path: Path) -> None:
    wf = make_workflow([{"id": "f", "tool": "fail", "ok_exit_codes": [0, 3]}])
    result, _ = run(tmp_path, wf)
    assert result.status == "success" and result.results["f"].ok


def test_abort_step_message_wait(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            {"id": "m", "kind": "message", "text": "hi {{ var.v }}"},
            {"id": "w", "kind": "wait", "seconds": 0.2},
            {"id": "stop", "kind": "abort", "text": "Ende", "exit_code": 7},
            echo("never", "x"),
        ],
        {"v": {"default": "there"}},
    )
    start = time.monotonic()
    result, events = run(tmp_path, wf)
    assert time.monotonic() - start >= 0.2
    assert (result.status, result.message, result.exit_code) == ("aborted", "Ende", 7)
    assert Message("m", "hi there") in events and "never" not in result.results


def test_secret_masked_everywhere(tmp_path: Path) -> None:
    wf = make_workflow([echo("a", "pw={{ var.pw }}")], {"pw": {"type": "secret"}})
    result, events = run(tmp_path, wf, {"pw": "hunter2"})
    step = result.results["a"]
    assert "hunter2" not in " ".join(step.argv) and "hunter2" not in step.command
    assert "***" in step.command and step.stdout == "pw=***\n"
    assert result.variables["pw"] == "***"
    shown = [e.command if isinstance(e, StepStarted) else getattr(e, "text", "") for e in events]
    assert not any("hunter2" in text for text in shown)
    assert "pw=***\n" in shown


def test_env_blocklist(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            {
                "id": "a",
                "tool": "env-dump",
                "extra_args": ["LD_PRELOAD"],
                "env": {"LD_PRELOAD": "/x.so"},
            },
            {
                "id": "b",
                "tool": "env-dump",
                "extra_args": ["FOO"],
                "env": {"FOO": "{{ var.v }}", "BAD=": "1"},
            },
        ],
        {"v": {"default": "bar"}},
    )
    result, events = run(tmp_path, wf)
    assert result.results["a"].stdout == "UNSET\n" and result.results["b"].stdout == "bar\n"
    warnings = [e.text for e in events if isinstance(e, Message)]
    assert any("LD_PRELOAD" in w and "WARNUNG" in w for w in warnings)
    assert any("BAD=" in w for w in warnings)


def test_confirmation_refused_starts_no_process(tmp_path: Path, tools: Path) -> None:
    asked: list[ConfirmRequest] = []

    def refuse(request: ConfirmRequest) -> bool:
        asked.append(request)
        return False

    result, _ = run(tmp_path, make_workflow([{"id": "r", "tool": "git"}]), confirm=refuse)
    assert result.status == "aborted" and "abgelehnt" in result.message
    assert [a.step_id for a in asked] == ["r"] and asked[0].safety.value == "caution"
    assert not tools.exists()
    result, _ = run(tmp_path, make_workflow([{"id": "r", "tool": "git"}]))
    assert result.status == "success" and tools.read_text() == "run\n"


def test_controller_abort_kills_running_step(tmp_path: Path) -> None:
    controller = Controller()
    threading.Timer(0.3, controller.abort.set).start()
    start = time.monotonic()
    result, events = run(
        tmp_path,
        make_workflow([{"id": "n", "tool": "napper"}, echo("never", "x")]),
        controller=controller,
    )
    assert time.monotonic() - start < 2
    assert result.status == "aborted" and result.message == "Abgebrochen"
    assert "never" not in result.results and isinstance(events[-1], WorkflowFinished)


def test_pause_blocks_until_released(tmp_path: Path) -> None:
    controller = Controller()
    controller.pause.set()
    threading.Timer(0.3, controller.pause.clear).start()
    start = time.monotonic()
    run(tmp_path, make_workflow([echo("a", "x")]), controller=controller)
    assert time.monotonic() - start >= 0.3


def test_step_mode_waits_for_release(tmp_path: Path) -> None:
    controller = Controller(step_mode=True)
    wf = make_workflow([echo("a", "x"), echo("b", "y")])
    runner, events = make_runner(tmp_path, controller=controller)
    prepared = runner.prepare(wf, {})
    worker = threading.Thread(target=runner.run, args=(prepared,))
    worker.start()
    time.sleep(0.3)
    assert not any(isinstance(e, StepStarted) for e in events)
    controller.step_release.set()
    time.sleep(0.4)
    assert [e.step_id for e in events if isinstance(e, StepStarted)] == ["a"]
    controller.step_release.set()
    worker.join(2)
    assert not worker.is_alive()
    assert [e.step_id for e in events if isinstance(e, StepStarted)] == ["a", "b"]


def test_output_limit_fails_step(tmp_path: Path) -> None:
    result, _ = run(tmp_path, make_workflow([echo("a", "x" * 5000)]), output_limit=100)
    assert result.status == "failed" and result.results["a"].truncated


def test_template_error_is_step_failure(tmp_path: Path) -> None:
    wf = make_workflow([echo("a", "{{ var.unset }}")], {"unset": {}})
    result, _ = run(tmp_path, wf)
    assert result.status == "failed" and "Unbekannte Variable" in result.message


_NEEDED = ("find", "grep", "wc", "tee")


@pytest.mark.skipif(any(shutil.which(t) is None for t in _NEEDED), reason="find/grep/wc/tee fehlen")
@pytest.mark.parametrize("with_errors", [True, False])
def test_bundled_log_errors_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_errors: bool
) -> None:
    # real PATH: undo the `tools` fixture
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "a.log").write_text(
        "INFO ok\nERROR disk\nERROR net\n" if with_errors else "INFO ok\n"
    )
    registry = ModuleRegistry([MODULES_DIR])
    registry.scan()
    events: list[Event] = []
    runner = Runner(
        Catalog(cache_dir=tmp_path / "cache", registry=registry),
        confirm=lambda request: True,
        on_event=events.append,
        cwd=tmp_path,
    )
    workflow = load_workflow_file(WORKFLOWS_DIR / "log_errors.workflow.yaml")
    result = runner.run(runner.prepare(workflow, {}))
    assert result.status == "success", result.message
    report = tmp_path / "bericht.txt"
    if with_errors:
        assert "Treffer" in report.read_text()
    else:
        assert not report.exists() and Message("ok", "Alles in Ordnung.") in events


def test_runtime_class_from_rendered_values(tmp_path: Path, tools: Path) -> None:
    wf = make_workflow(
        [{"id": "f", "tool": "find", "extra_args": ["{{ var.x }}"]}], {"x": {"default": "-name"}}
    )
    asked: list[ConfirmRequest] = []

    def refuse(request: ConfirmRequest) -> bool:
        asked.append(request)
        return False

    runner, _ = make_runner(tmp_path, confirm=refuse)
    assert runner.prepare(wf, {}).verdicts["f"].safety.value == "safe"
    assert run(tmp_path, wf, confirm=refuse)[0].status == "success"  # benign value, no question
    assert asked == [] and tools.read_text() == "run\n"
    tools.unlink()
    result, _ = run(tmp_path, wf, {"x": "-delete"}, confirm=refuse)
    assert result.status == "aborted" and [a.safety.value for a in asked] == ["dangerous"]
    assert not tools.exists()


def test_secret_in_extra_args_never_leaks(tmp_path: Path) -> None:
    wf = make_workflow(
        [
            {"id": "bad", "tool": "echo-args", "args": {"verbose": "x{{ var.pw }}"}},
            echo("a", "{{ var.pw }}"),
        ],
        {"pw": {"type": "secret"}},
    )
    runner, _ = make_runner(tmp_path)
    seen: list[Event] = []
    runner._on_event = seen.append  # noqa: SLF001
    result = runner.run(runner.prepare(wf, {"pw": "hunter2"}))
    assert "hunter2" not in repr(seen) and "hunter2" not in repr(result)
    assert result.status == "failed"


def test_cwd_stdin_file_env_raise_class_and_show_in_command(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    inside_dir = tmp_path / "work"
    inside_dir.mkdir()
    (outside / "f.txt").write_text("data")
    asked: list[ConfirmRequest] = []

    def yes(request: ConfirmRequest) -> bool:
        asked.append(request)
        return True

    wf = make_workflow(
        [
            {"id": "a", "tool": "echo-args", "cwd": str(outside)},
            {"id": "b", "tool": "mycat", "stdin": {"file": str(outside / "f.txt")}},
            {"id": "c", "tool": "env-dump", "extra_args": ["K"], "env": {"K": "v w"}},
            {"id": "d", "tool": "echo-args", "cwd": "."},
        ]
    )
    result, _ = run(inside_dir, wf, confirm=yes)
    assert result.results["b"].stdout == "data"
    assert [(r.step_id, r.reasons) for r in asked] == [
        ("a", ("Arbeitsverzeichnis außerhalb des Workflow-Ordners",)),
        ("b", ("liest Datei außerhalb",)),
        ("c", ("setzt Umgebungsvariablen",)),
    ]
    assert f"(in {outside.resolve()})" in asked[0].command
    assert f"< {outside.resolve() / 'f.txt'}" in asked[1].command
    assert asked[2].command.startswith("env 'K=v w' env-dump")


def test_nul_in_cwd_is_step_error(tmp_path: Path) -> None:
    wf = make_workflow([{"id": "a", "tool": "echo-args", "cwd": "a\x00b"}])
    result, _ = run(tmp_path, wf)
    assert result.status == "failed" and "null" in result.results["a"].stderr


def test_more_blocked_env_keys(tmp_path: Path) -> None:
    env = {"NODE_OPTIONS": "x", "GIT_CONFIG_COUNT": "1", "PAGER": "x", "OK_KEY": "1"}
    wf = make_workflow([{"id": "a", "tool": "echo-args", "env": env}])
    _, events = run(tmp_path, wf)
    warned = [e.text for e in events if isinstance(e, Message)]
    assert len(warned) == 3 and not any("OK_KEY" in w for w in warned)


def test_type_error_message_has_no_value(tmp_path: Path) -> None:
    wf = make_workflow([echo("a", "x")], {"pw": {"type": "int"}})
    runner, _ = make_runner(tmp_path)
    with pytest.raises(RunError, match="Variable 'pw'") as caught:
        runner.prepare(wf, {"pw": "s3cret-value"})
    assert "s3cret" not in str(caught.value)


@pytest.mark.parametrize(
    ("spec", "value", "message"),
    [
        ({"type": "enum", "choices": ["a", "b"]}, "c", "keine erlaubte Auswahl"),
        ({"type": "int", "min": 2}, "1", "kleiner als das Minimum"),
        ({"type": "float", "max": 1.5}, "2", "größer als das Maximum"),
    ],
)
def test_choices_and_bounds_rejected(
    tmp_path: Path, spec: dict[str, Any], value: str, message: str
) -> None:
    wf = make_workflow([echo("a", "x")], {"v": spec})
    runner, _ = make_runner(tmp_path)
    with pytest.raises(RunError, match=message):
        runner.prepare(wf, {"v": value})
    ok = {"enum": "a", "int": "2", "float": "1.5"}[spec["type"]]
    runner.prepare(wf, {"v": ok})
