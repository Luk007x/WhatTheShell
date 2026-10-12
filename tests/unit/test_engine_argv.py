# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest

from whattheshell.engine import ArgvError, build_argv, display
from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import InputSpec, OptionSpec, ValueType


def make(*options: OptionSpec, inputs: list[InputSpec] | None = None) -> CommandSpec:
    return CommandSpec(name=["tool", "sub"], options=list(options), inputs=inputs or [])


def opt(id_: str, flags: list[str], **kw: object) -> OptionSpec:
    return OptionSpec(id=id_, flags=flags, **kw)


def test_subcommand_path_tool_path_extra_args() -> None:
    spec = make()
    assert build_argv(spec, {}, ["-x", "a b"], tool_path="/usr/bin/tool") == [
        "/usr/bin/tool",
        "sub",
        "-x",
        "a b",
    ]


def test_bool_prefers_long_flag_and_false_is_omitted() -> None:
    spec = make(opt("v", ["-v", "--verbose"]), opt("q", ["-q"]))
    assert build_argv(spec, {"v": True, "q": False}) == ["tool", "sub", "--verbose"]
    assert build_argv(spec, {"v": "false", "q": "true"}) == ["tool", "sub", "-q"]


def test_value_multiple_nargs_attached() -> None:
    spec = make(
        opt("n", ["-n"], type=ValueType.int),
        opt("e", ["-e"], type=ValueType.string, multiple=True),
        opt("p", ["--pair"], type=ValueType.string, nargs=2),
        opt("c", ["-C", "--color"], type=ValueType.string, attached=True),
        opt("s", ["-s"], type=ValueType.string, attached=True),
    )
    args = {"n": 3, "e": ["a", "b"], "p": ["x", "y"], "c": "auto", "s": "v"}
    assert build_argv(spec, args) == [
        *("tool", "sub", "-n", "3", "-e", "a", "-e", "b"),
        *("--pair", "x", "y", "--color=auto", "-s", "v"),
    ]


def test_nargs_wrong_length() -> None:
    spec = make(opt("p", ["--pair"], type=ValueType.string, nargs=2))
    with pytest.raises(ArgvError, match="pair|'p'"):
        build_argv(spec, {"p": ["x"]})


def test_enum_and_number_errors() -> None:
    spec = make(
        opt("w", ["--when"], type=ValueType.enum, choices=["a", "b"]),
        opt("n", ["-n"], type=ValueType.int),
    )
    with pytest.raises(ArgvError, match="Erlaubt: a, b"):
        build_argv(spec, {"w": "c"})
    with pytest.raises(ArgvError, match="keine Zahl"):
        build_argv(spec, {"n": "x"})
    assert build_argv(spec, {"w": "a"}) == ["tool", "sub", "--when", "a"]


def test_inputs_order_required_multiple() -> None:
    spec = make(
        inputs=[
            InputSpec(id="b", position=2, multiple=True),
            InputSpec(id="a", position=1, required=True),
        ]
    )
    assert build_argv(spec, {"a": "1", "b": ["2", "3"]}) == ["tool", "sub", "1", "2", "3"]
    with pytest.raises(ArgvError, match="Pflichteingabe fehlt"):
        build_argv(spec, {"b": ["2"]})


def test_unknown_key() -> None:
    spec = make(opt("v", ["-v"]))
    with pytest.raises(ArgvError, match="Unbekanntes Feld 'x' für tool, bekannte Felder: v"):
        build_argv(spec, {"x": 1})


@pytest.mark.parametrize("value", ["; rm -rf /", "$(id)", "a b", 'it\'s "q"', "`id`"])
def test_special_characters_stay_one_element(value: str) -> None:
    spec = make(opt("o", ["--out"], type=ValueType.string), inputs=[InputSpec(id="f")])
    argv = build_argv(spec, {"o": value, "f": value}, [value])
    assert argv == ["tool", "sub", "--out", value, value, value]
    assert display(argv).count(value) <= 3


def test_before_options_inputs_come_first() -> None:
    spec = make(
        opt("name", ["-name"], type=ValueType.string),
        inputs=[
            InputSpec(id="start", before_options=True),
            InputSpec(id="rest"),
        ],
    )
    argv = build_argv(spec, {"name": "*.log", "start": "dir", "rest": "r"}, ["-x"])
    assert argv == ["tool", "sub", "dir", "-name", "*.log", "r", "-x"]


def test_single_value_option_rejects_list() -> None:
    spec = make(opt("name", ["-name"], type=ValueType.string))
    with pytest.raises(ArgvError, match="Option 'name' erwartet einen einzelnen Wert, bekam Liste"):
        build_argv(spec, {"name": ["a", "b"]})
