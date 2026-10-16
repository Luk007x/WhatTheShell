# SPDX-License-Identifier: AGPL-3.0-or-later
"""Agent command allowlist, model and reasoning fields, built-in command lines."""

import pytest
from pydantic import ValidationError

from whattheshell.ai.providers import build
from whattheshell.ai.providers.agent_cli import AgentCliProvider, _default_command
from whattheshell.settings import AgentSettings, AiSettings, validate_command


def _without(line: list[str], flag: str, values: int = 0) -> list[str]:
    at = line.index(flag)
    return line[:at] + line[at + 1 + values :]


def test_built_in_lines_are_valid() -> None:
    for kind in ("claude", "codex"):
        validate_command(kind, _default_command(kind, "m1", "high"))
        validate_command(kind, _default_command(kind))


@pytest.mark.parametrize(
    ("kind", "mutate", "text"),
    [
        ("codex", lambda c: [*c[:-1], "-o", "~/x", "-"], "doppelt"),
        ("codex", lambda c: [*_without(c, "-o", 1), "-o", "~/x"], "nicht erlaubt"),
        ("codex", lambda c: [*_without(c, "-C", 1), "-C", "/repo"], "nicht erlaubt"),
        ("claude", lambda c: ["/tmp/claude", *c[1:]], "genau"),
        ("claude", lambda c: [*c, "--permission-mode", "dontAsk"], "doppelt"),
        ("claude", lambda c: [*_without(c, "--permission-mode", 1), "--permission-mode", "plan"],
         "nicht erlaubt"),
        ("claude", lambda c: _without(c, "--strict-mcp-config"), "Pflichtteil"),
        ("codex", lambda c: _without(c, "exec"), "exec"),
        ("codex", lambda c: [*c[:-1], "-c", "sandbox_mode=x", "-"], "nicht erlaubt"),
        ("codex", lambda c: [*c[:-1], "-c", "model_reasoning_effort=max", "-"], "nicht erlaubt"),
        ("claude", lambda c: [*c, "--dangerously-skip-permissions"], "nicht erlaubt"),
    ],
)  # fmt: skip
def test_bad_lines_rejected(kind: str, mutate, text: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=text):
        validate_command(kind, mutate(_default_command(kind)))


def test_model_and_reasoning_fields() -> None:
    assert AgentSettings(model="claude-opus-5-5").model == "claude-opus-5-5"
    for bad in ("-x", "a b", "x" * 65):
        with pytest.raises(ValidationError):
            AgentSettings(model=bad)
    with pytest.raises(ValidationError):
        AgentSettings(reasoning="max")  # type: ignore[arg-type]


def test_command_key_no_longer_supported() -> None:
    with pytest.raises(ValidationError, match="ai.agent.command"):
        AgentSettings.model_validate({"command": ["claude"]})


def test_default_commands_carry_model_and_reasoning() -> None:
    claude = _default_command("claude", "opus")
    assert claude[-2:] == ["--model", "opus"] and "--tools" in claude
    codex = _default_command("codex", "m1", "low")
    assert "-m" in codex and 'model_reasoning_effort="low"' in codex and codex[-1] == "-"
    AgentCliProvider("codex", 5, "m1", "high")


def test_build_passes_model_and_reasoning() -> None:
    def argv(**agent: str) -> list[str]:
        provider = build(AiSettings(provider="agent", agent=AgentSettings(**agent)))  # type: ignore[arg-type]
        return provider._command  # type: ignore[attr-defined, no-any-return]

    claude = argv(model="opus")
    assert claude[claude.index("--model") + 1] == "opus"
    codex = argv(kind="codex", model="m1", reasoning="high")
    assert codex[codex.index("-m") + 1] == "m1"
    assert 'model_reasoning_effort="high"' in codex
    plain = argv(kind="codex")
    assert "-m" not in plain and not any("model_reasoning" in part for part in plain)
    assert "--model" not in argv()
