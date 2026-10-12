# SPDX-License-Identifier: AGPL-3.0-or-later
"""Section detection, subcommands, inputs and the fallback on three miniatures."""

from whattheshell.helpparse import parse_help
from whattheshell.helpparse.sections import split_sections
from whattheshell.models.common import Confidence, ValueType

GNU = """\
Usage: grep [OPTION]... PATTERNS [FILE]...
Search for PATTERNS in each FILE.

Pattern selection:
  -E, --extended-regexp     PATTERNS are extended regular expressions
  -i, --ignore-case         ignore case distinctions

Examples:
  grep -i 'hello world' menu.h main.c
"""

COBRA = """\
Manage pods, containers and images

Usage:
  podman [options] [command]

Available Commands:
  attach      Attach to a running container
  auto-update Auto update containers
  build       Build an image

Options:
      --log-level string   Log messages above specified level (default "warn")
  -h, --help               Help for podman
"""

USAGE_ONLY = """\
usage: ssh [-46A] [-B bind_interface]
           [-p port] destination [command [argument ...]]
       ssh [-Q query_option]
"""


def kinds(text: str) -> list[str]:
    return [s.kind for s in split_sections(text)]


def test_gnu_sections() -> None:
    assert kinds(GNU) == ["usage", "other", "other", "examples"]


def test_cobra_sections() -> None:
    assert kinds(COBRA) == ["preamble", "usage", "commands", "options"]


def test_usage_only_is_one_section_with_all_statements() -> None:
    sections = split_sections(USAGE_ONLY)
    assert [s.kind for s in sections] == ["usage"]
    assert len(sections[0].lines) == 3


def test_gnu_parse() -> None:
    spec = parse_help(GNU, ["grep"])
    assert spec.summary == "Search for PATTERNS in each FILE."
    assert [o.flags for o in spec.options] == [["-E", "--extended-regexp"], ["-i", "--ignore-case"]]
    patterns, file = spec.inputs
    assert (patterns.id, patterns.required, patterns.multiple) == ("patterns", True, False)
    assert (file.id, file.required, file.multiple, file.type) == (
        "file",
        False,
        True,
        ValueType.path,
    )
    assert spec.raw_help == GNU


def test_cobra_parse() -> None:
    spec = parse_help(COBRA, ["podman"])
    assert [c.name for c in spec.subcommands] == [
        ["podman", "attach"],
        ["podman", "auto-update"],
        ["podman", "build"],
    ]
    assert spec.subcommands[1].summary == "Auto update containers"
    assert spec.subcommands[0].options == []
    assert [o.flags for o in spec.options] == [["--log-level"], ["-h", "--help"]]
    assert spec.options[0].default == "warn"


def test_usage_only_parse() -> None:
    spec = parse_help(USAGE_ONLY, ["ssh"])
    assert {"-4", "-A", "-B", "-p", "-Q"} <= {f for o in spec.options for f in o.flags}


def test_iproute_object_list() -> None:
    text = "Usage: ip OBJECT { COMMAND | help }\nwhere  OBJECT := { address | link |\n  route }\n"
    assert [c.name[-1] for c in parse_help(text, ["ip"]).subcommands] == [
        "address",
        "link",
        "route",
    ]


def test_usage_subcommands() -> None:
    text = "Usage: ip address {add|change} IFADDR\n       ip address del IFADDR\n"
    spec = parse_help(text, ["ip", "address"])
    assert [c.name[-1] for c in spec.subcommands] == ["add", "change", "del"]


def test_git_style_groups_with_blank_lines() -> None:
    text = (
        "usage: git <command>\n\nThese are common Git commands:\n\n"
        "start\n   clone   Clone it\n\nwork\n   add     Add it\n"
    )
    assert [c.name[-1] for c in parse_help(text, ["git"]).subcommands] == ["clone", "add"]


def test_fallback_for_unparsable_text() -> None:
    spec = parse_help("hello world\nnothing useful\n", ["x"])
    assert spec.confidence is Confidence.low
    assert (spec.summary, spec.options, spec.inputs, spec.subcommands) == (
        "hello world",
        [],
        [],
        [],
    )
    assert spec.raw_help == "hello world\nnothing useful\n"


def test_empty_text_does_not_raise() -> None:
    spec = parse_help("", ["x"])
    assert spec.confidence is Confidence.low
    assert spec.raw_help == ""
