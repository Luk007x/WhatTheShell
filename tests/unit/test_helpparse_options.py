# SPDX-License-Identifier: AGPL-3.0-or-later
"""Option line forms, type derivation, defaults, confidence and ids."""

import re
import time

import pytest

from whattheshell.helpparse import parse_help
from whattheshell.models.common import ID_PATTERN, Confidence, OptionSpec, ValueType


def options_of(body: str) -> list[OptionSpec]:
    return parse_help(f"Options:\n{body}\n", ["x"]).options


def one(body: str) -> OptionSpec:
    options = options_of(body)
    assert len(options) == 1, options
    return options[0]


@pytest.mark.parametrize(
    ("line", "flags", "type_", "choices"),
    [
        ("  -x, --long=ARG   do things", ["-x", "--long"], "string", []),
        ("  -x ARG           do things", ["-x"], "string", []),
        ("      --long[=ARG] do things", ["--long"], "string", []),
        ("      --long ARG   do things", ["--long"], "string", []),
        ("  -x, --long ARG   do things", ["-x", "--long"], "string", []),
        ("      --[no-]flag  do things", ["--flag", "--no-flag"], "bool", []),
        ("  -x/--long        do things", ["-x", "--long"], "bool", []),
        ("  -x | --long      do things", ["-x", "--long"], "bool", []),
        ("  -NUM             do things", ["-NUM"], "bool", []),
        ("  -i infile        do things", ["-i"], "path", []),
        ("  -B bind_address  do things", ["-B"], "string", []),
        ("  -d[file]         --dump[=file]", ["-d", "--dump"], "path", []),
        ("  -q --quiet       do things", ["-q", "--quiet"], "bool", []),
        ("  -c, -C NUM, --context[=NUM]  lines", ["-c", "-C", "--context"], "int", []),
        ("  -f FILE          read FILE", ["-f"], "path", []),
        ("  -d, --dir=DIR    in DIR", ["-d", "--dir"], "path", []),
        ("  --port PORT      listen", ["--port"], "int", []),
        ("  --mode {a,b,c}   pick one", ["--mode"], "enum", ["a", "b", "c"]),
        ("  --retries int    how often", ["--retries"], "int", []),
        ("  --connect <seconds>  limit", ["--connect"], "int", []),
        ("  --cookie <data|filename>  free text", ["--cookie"], "string", []),
    ],
)
def test_forms_and_types(line: str, flags: list[str], type_: str, choices: list[str]) -> None:
    option = one(line)
    assert (option.flags, option.type.value, option.choices) == (flags, type_, choices)


def test_enum_from_quoted_list() -> None:
    option = one("  --color[=WHEN]  colorize; WHEN is 'always', 'never', or 'auto'")
    assert (option.type, option.choices) == (ValueType.enum, ["always", "never", "auto"])


def test_enum_from_one_of() -> None:
    option = one("  --sort=KEY  sort by KEY, one of: name, size, time")
    assert (option.type, option.choices) == (ValueType.enum, ["name", "size", "time"])


def test_enum_from_pipe_list_in_brackets() -> None:
    option = one("  -L[fatal|invalid]  lint")
    assert (option.type, option.choices) == (ValueType.enum, ["fatal", "invalid"])


@pytest.mark.parametrize(
    ("line", "default"),
    [
        ("  -n, --num=N  count (default: 5)", 5),
        ("  -n, --num=N  count (default 7)", 7),
        ("  -n, --num=N  count [default: 9]", 9),
        ("  --name=NAME  who (default: bob)", "bob"),
    ],
)
def test_default_detection(line: str, default: object) -> None:
    assert one(line).default == default


def test_no_default_for_default_if_omitted() -> None:
    assert one("  --color[=WHEN]  colorize (default if omitted)").default is None


def test_multi_line_description() -> None:
    option = one("  -a, --all\n         first line\n         second line")
    assert option.help == "first line second line"


def test_description_stops_at_next_option() -> None:
    options = options_of("  -a, --all   do a\n         more a\n  -b, --bee  do b")
    assert [o.help for o in options] == ["do a more a", "do b"]


def test_packed_find_style_line() -> None:
    options = options_of("      -amin N -anewer FILE -empty")
    assert [(o.flags, o.type.value) for o in options] == [
        (["-amin"], "int"),
        (["-anewer"], "path"),
        (["-empty"], "bool"),
    ]


@pytest.mark.parametrize(
    ("line", "confidence"),
    [
        ("  -x, --long=NUM   do things", Confidence.high),
        ("  -x, --long       do things", Confidence.high),
        ("  -x               do things", Confidence.medium),
        ("  --long=THING     do things", Confidence.medium),
        ("  -x, --long\n         described below", Confidence.medium),
        ("  -x, --long", Confidence.low),
    ],
)
def test_confidence(line: str, confidence: Confidence) -> None:
    assert one(line).confidence is confidence


def test_usage_derivation_is_low_confidence() -> None:
    spec = parse_help("usage: ssh [-46Aa] [-B bind_interface] [-p port]\n", ["ssh"])
    by_flag = {o.flags[0]: o for o in spec.options}
    assert {"-4", "-6", "-A", "-a", "-B", "-p"} <= by_flag.keys()
    assert by_flag["-4"].type is ValueType.bool
    assert (by_flag["-B"].type, by_flag["-p"].type) == (ValueType.string, ValueType.int)
    assert {o.confidence for o in spec.options} == {Confidence.low}


def test_ids_are_valid_and_unique() -> None:
    options = options_of(
        "  -c   lower\n  -C   upper\n  -4   four\n  -NUM  num\n"
        "  --dry-run  one\n  --dry_run  two\n  --Dry-Run  three\n  --[no-]x  x"
    )
    ids = [o.id for o in options]
    assert len(ids) == len(set(ids)) == 8
    assert all(re.fullmatch(ID_PATTERN, i) for i in ids)
    assert ids[:5] == ["c", "c_upper", "opt_4", "num", "dry_run"]
    assert ids[5:7] == ["dry_run_2", "dry_run_3"]


def test_duplicate_flags_are_dropped() -> None:
    assert len(options_of("  -a, --all   one\n  --all   again")) == 1


def test_prose_is_not_an_option() -> None:
    assert options_of("  --diff, --extract or --list and when a list of files") == []


def test_huge_line_is_fast_and_rejected() -> None:
    start = time.perf_counter()
    assert options_of("  " + "-a, " * 150_000) == []
    assert time.perf_counter() - start < 2


def test_long_flag_list_is_linear() -> None:
    start = time.perf_counter()
    assert len(one("  " + "-a, " * 200 + "--all  x").flags) == 201
    assert time.perf_counter() - start < 2


@pytest.mark.parametrize("word", ["FILE", "DIR", "PATH", "INFILE", "NUM"])
def test_input_and_option_type_agree(word: str) -> None:
    from_input = parse_help(f"Usage: x {word}\n", ["x"]).inputs[0].type
    from_option = one(f"  --opt {word}  something").type
    assert from_input == from_option or (from_input is ValueType.string and word == "NUM")


def test_usage_pipe_alternatives() -> None:
    spec = parse_help("usage: g [-v | --version] [-p | --paginate | -P | --no-pager]\n", ["g"])
    assert [o.flags for o in spec.options] == [
        ["-v", "--version"],
        ["-p"],
        ["--paginate"],
        ["-P"],
        ["--no-pager"],
    ]
