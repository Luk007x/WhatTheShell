# SPDX-License-Identifier: AGPL-3.0-or-later
"""Acceptance: hostile values reach the program as exactly one argument, stdin text or env value."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from .test_engine_runner import echo, make_runner, make_workflow, tools  # noqa: F401

PWNED = Path("/tmp/wts_pwned")  # noqa: S108 (the value the payloads try to create)

PAYLOADS = [
    "; rm -rf /tmp/wts_pwned",
    "$(touch /tmp/wts_pwned)",
    "`id`",
    "a b  c",
    '"quoted"',
    "'single'",
    "\\n",
    "--not-an-option",
    "Ünïcödé ✓ 日本",
]


@pytest.fixture(autouse=True)
def _no_pwned_file() -> Iterator[None]:
    PWNED.unlink(missing_ok=True)
    assert not PWNED.exists()
    yield
    PWNED.unlink(missing_ok=True)


pytestmark = pytest.mark.usefixtures("tools")


def _run(tmp_path: Path, steps: list[dict[str, Any]], value: str) -> dict[str, str]:
    runner, _ = make_runner(tmp_path)
    workflow = make_workflow(steps, {"v": {}})
    result = runner.run(runner.prepare(workflow, {"v": value}))
    assert result.status == "success", result.message
    assert not PWNED.exists()
    return {step_id: step.stdout for step_id, step in result.results.items()}


@pytest.mark.parametrize("payload", PAYLOADS)
def test_args_extra_args_and_variables_stay_single_arguments(tmp_path: Path, payload: str) -> None:
    # `arg` input via args, plain extra_args, and a template from a variable
    steps = [
        {"id": "a", "tool": "echo-args", "args": {"arg": [payload]}},
        echo("b", payload),
        echo("c", "{{ var.v }}"),
    ]
    out = _run(tmp_path, steps, payload)
    assert out == {"a": payload + "\n", "b": payload + "\n", "c": payload + "\n"}


@pytest.mark.parametrize("payload", PAYLOADS)
def test_stdin_text_is_data(tmp_path: Path, payload: str) -> None:
    steps = [{"id": "a", "tool": "mycat", "stdin": {"text": "{{ var.v }}"}}]
    assert _run(tmp_path, steps, payload) == {"a": payload}


@pytest.mark.parametrize("payload", PAYLOADS)
def test_env_value_is_data(tmp_path: Path, payload: str) -> None:
    steps = [
        {"id": "a", "tool": "env-dump", "extra_args": ["WTS_X"], "env": {"WTS_X": "{{ var.v }}"}}
    ]
    assert _run(tmp_path, steps, payload) == {"a": payload + "\n"}
