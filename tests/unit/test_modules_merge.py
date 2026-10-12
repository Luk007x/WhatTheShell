# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

from whattheshell import bundled
from whattheshell.helpparse import parse_help
from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import Confidence, OptionSpec, ValueType
from whattheshell.models.module import Module
from whattheshell.modules.loader import load_module_file
from whattheshell.modules.merge import apply_modules, merge_command
from whattheshell.modules.registry import LoadedModule

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


def catalog() -> CommandSpec:
    return CommandSpec(
        name=["t"],
        summary="cat",
        confidence=Confidence.low,
        options=[
            OptionSpec(id="a", flags=["-a"], type=ValueType.int, confidence=Confidence.low),
            OptionSpec(id="b", flags=["-b"]),
        ],
        subcommands=[
            CommandSpec(name=["t", "sub"], options=[OptionSpec(id="x", flags=["-x"])]),
        ],
    )


def module(**fields: object) -> Module:
    return Module.model_validate({"schema_version": 1, "tool": "t", **fields})


def loaded(mod: Module, priority: int = 0) -> LoadedModule:
    return LoadedModule(Path("m.module.yaml"), mod, priority)


def test_option_override_keeps_unset_fields() -> None:
    mod = module(options=[{"id": "a", "label": "L", "help": "H", "group": "G"}])
    result = merge_command(catalog(), mod, replace=False)
    a = result.options[0]
    assert (a.label, a.help, a.group) == ("L", "H", "G")
    assert a.type == ValueType.int
    assert a.flags == ["-a"]
    assert a.confidence == Confidence.high
    assert result.options[1].id == "b"
    assert result.summary == "cat"


def test_unknown_option_appended() -> None:
    result = merge_command(catalog(), module(options=[{"id": "n"}]), replace=False)
    assert [o.id for o in result.options] == ["a", "b", "n"]


def test_catalog_confidence_kept_for_untouched() -> None:
    result = merge_command(catalog(), module(summary="m"), replace=False)
    assert result.options[0].confidence == Confidence.low
    assert result.summary == "m"


def test_replace_drops_catalog() -> None:
    spec = catalog().model_copy(update={"raw_help": "raw"})
    result = merge_command(spec, module(options=[{"id": "n"}]), replace=True)
    assert [o.id for o in result.options] == ["n"]
    assert result.subcommands == []
    assert result.summary is None
    assert result.raw_help == "raw"


def test_subcommands_recursive() -> None:
    mod = module(
        subcommands=[
            {"name": "sub", "options": [{"id": "x", "label": "X"}], "summary": "s"},
            {"name": "new", "options": [{"id": "y"}]},
        ]
    )
    result = merge_command(catalog(), mod, replace=False)
    sub, new = result.subcommands
    assert sub.options[0].label == "X"
    assert sub.options[0].flags == ["-x"]
    assert sub.summary == "s"
    assert new.name == ["t", "new"]
    assert [o.id for o in new.options] == ["y"]


def test_chain_of_two_modules() -> None:
    first = loaded(module(options=[{"id": "a", "label": "one", "help": "h1"}]))
    second = loaded(module(options=[{"id": "a", "label": "two"}]), 1)
    a = apply_modules(catalog(), [first, second]).options[0]
    assert (a.label, a.help) == ("two", "h1")


def test_replace_then_merge_in_chain() -> None:
    first = loaded(module(override_mode="replace", options=[{"id": "n"}]))
    second = loaded(module(options=[{"id": "m"}]), 1)
    assert [o.id for o in apply_modules(catalog(), [first, second]).options] == ["n", "m"]


def test_inputs_not_mutated() -> None:
    spec = catalog()
    mod = module(
        options=[{"id": "a", "label": "L"}, {"id": "n"}],
        subcommands=[{"name": "sub", "summary": "s"}],
        examples=[{"title": "e"}],
    )
    before_spec, before_mod = spec.model_dump(), mod.model_dump()
    merge_command(spec, mod, replace=False)
    merge_command(spec, mod, replace=True)
    assert spec.model_dump() == before_spec
    assert mod.model_dump() == before_mod


def test_examples_and_i18n_appended() -> None:
    first = module(
        examples=[{"title": "e1"}],
        i18n={"en": {"summary": "S", "options": {"a": {"label": "A"}}}},
        templates=[{"title": "t", "workflow": "w.yaml"}],
    )
    second = module(
        examples=[{"title": "e2"}],
        i18n={"en": {"options": {"b": {"label": "B"}}}, "fr": {"summary": "F"}},
    )
    result = apply_modules(catalog(), [loaded(first), loaded(second, 1)])
    assert [e.title for e in result.examples] == ["e1", "e2"]
    assert [t.title for t in result.templates] == ["t"]
    assert result.i18n["en"].summary == "S"
    assert set(result.i18n["en"].options) == {"a", "b"}
    assert result.i18n["fr"].summary == "F"


def test_bundled_grep_over_parsed_help() -> None:
    mod = load_module_file(bundled.MODULES_DIR / "grep.module.yaml")
    parsed = parse_help((CORPUS / "grep" / "stdout.txt").read_text(), ["grep"])
    plain = {o.id: o for o in parsed.options}
    result = apply_modules(parsed, [loaded(mod)])
    merged = {o.id: o for o in result.options}
    assert merged["ignore_case"].label == "Groß-/Kleinschreibung ignorieren"
    untouched = next(i for i in plain if i not in {o.id for o in mod.options})
    assert merged[untouched] == plain[untouched]


def test_interactive_override() -> None:
    from whattheshell.models.catalog import CommandSpec
    from whattheshell.models.module import CommandOverride
    from whattheshell.modules.merge import merge_command

    spec = CommandSpec(name=["x"])
    assert merge_command(spec, CommandOverride(interactive=True), replace=False).interactive
    assert not merge_command(spec, CommandOverride(), replace=False).interactive


def test_module_inputs_replace_catalog_inputs() -> None:
    from whattheshell.models.catalog import CommandSpec
    from whattheshell.models.common import InputSpec
    from whattheshell.models.module import CommandOverride
    from whattheshell.modules.merge import merge_command

    spec = CommandSpec(name=["x"], inputs=[InputSpec(id="file")])
    renamed = merge_command(spec, CommandOverride(inputs=[InputSpec(id="paths")]), replace=False)
    assert [i.id for i in renamed.inputs] == ["paths"]
    assert [i.id for i in merge_command(spec, CommandOverride(), replace=False).inputs] == ["file"]


def test_input_option_id_collision_gets_arg_suffix() -> None:
    from whattheshell.models.catalog import CommandSpec
    from whattheshell.models.common import InputSpec, OptionSpec
    from whattheshell.models.module import CommandOverride
    from whattheshell.modules.merge import merge_command

    spec = CommandSpec(name=["x"], inputs=[InputSpec(id="a")])
    merged = merge_command(spec, CommandOverride(options=[OptionSpec(id="a")]), replace=False)
    assert [i.id for i in merged.inputs] == ["a_arg"]
