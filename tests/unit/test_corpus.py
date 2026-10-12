# SPDX-License-Identifier: AGPL-3.0-or-later
"""Measure the help parser against the golden files in tests/corpus."""

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from whattheshell.helpparse import parse_help

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
FOLDERS = sorted(p for p in CORPUS.iterdir() if p.is_dir())
GOLDEN = [p for p in FOLDERS if (p / "expected.json").exists()]
PER_TOOL_RECALL = 0.75
TOTAL_RECALL = 0.90
TOTAL_SUBCOMMAND_RECALL = 0.90
TOTAL_TYPE_FIDELITY = 0.90


def corpus_text(folder: Path) -> str:
    """stdout.txt, or stderr.txt if stdout is empty."""
    return (folder / "stdout.txt").read_text() or (folder / "stderr.txt").read_text()


def command_name(folder: Path) -> list[str]:
    """Command words from meta.json, e.g. [git, commit] or, for ``python -m pip``, [pip]."""
    argv: list[str] = json.loads((folder / "meta.json").read_text())["argv"]
    if "-m" in argv:
        return [argv[argv.index("-m") + 1]]
    if os.path.basename(argv[0]) == "man":
        return [argv[-1]]
    words = [a for a in argv[1:] if not a.startswith("-") and a != "help"]
    return [os.path.basename(argv[0]), *words]


@dataclass(frozen=True)
class Measurement:
    """Counts for one tool."""

    options_expected: int
    options_found: int
    types_correct: int
    subcommands_expected: int
    subcommands_found: int
    missing_options: list[list[str]]
    missing_subcommands: list[str]


@cache
def measure(folder: Path) -> Measurement:
    """Parse one corpus folder and compare with its expected.json."""
    expected = json.loads((folder / "expected.json").read_text())
    spec = parse_help(corpus_text(folder), command_name(folder))
    by_flag = {flag: option for option in spec.options for flag in reversed(option.flags)}
    found = types_correct = 0
    missing: list[list[str]] = []
    for want in expected.get("options", []):
        option = next((by_flag[f] for f in want["flags"] if f in by_flag), None)
        if option is None:
            missing.append(want["flags"])
            continue
        found += 1
        types_correct += (
            option.type.value == want["type"]
            and (option.type.value != "bool") == want["takes_value"]
        )
    parsed_subs = {command.name[-1] for command in spec.subcommands}
    wanted_subs = expected.get("subcommands", [])
    missing_subs = [s for s in wanted_subs if s not in parsed_subs]
    return Measurement(
        len(expected.get("options", [])),
        found,
        types_correct,
        len(wanted_subs),
        len(wanted_subs) - len(missing_subs),
        missing,
        missing_subs,
    )


def test_corpus_is_not_empty() -> None:
    assert GOLDEN, "no tests/corpus/*/expected.json found"


@pytest.mark.parametrize("folder", GOLDEN, ids=lambda p: p.name)
def test_option_recall_per_tool(folder: Path) -> None:
    m = measure(folder)
    if m.options_expected:
        recall = m.options_found / m.options_expected
        assert recall >= PER_TOOL_RECALL, f"recall {recall:.2f}, missing {m.missing_options}"


def test_total_option_recall() -> None:
    results = [measure(f) for f in GOLDEN]
    expected = sum(m.options_expected for m in results)
    recall = sum(m.options_found for m in results) / expected
    missing = {f.name: measure(f).missing_options for f in GOLDEN if measure(f).missing_options}
    assert recall >= TOTAL_RECALL, f"recall {recall:.3f}, missing {missing}"


def test_total_type_fidelity() -> None:
    results = [measure(f) for f in GOLDEN]
    fidelity = sum(m.types_correct for m in results) / sum(m.options_found for m in results)
    assert fidelity >= TOTAL_TYPE_FIDELITY, f"type fidelity {fidelity:.3f}"


def test_total_subcommand_recall() -> None:
    results = [measure(f) for f in GOLDEN]
    recall = sum(m.subcommands_found for m in results) / sum(
        m.subcommands_expected for m in results
    )
    missing = {
        f.name: measure(f).missing_subcommands for f in GOLDEN if measure(f).missing_subcommands
    }
    assert recall >= TOTAL_SUBCOMMAND_RECALL, f"recall {recall:.3f}, missing {missing}"


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda p: p.name)
def test_parse_never_raises_and_keeps_raw_help(folder: Path) -> None:
    text = corpus_text(folder)
    spec = parse_help(text, command_name(folder))
    assert spec.raw_help == text
    assert spec.name == command_name(folder)
