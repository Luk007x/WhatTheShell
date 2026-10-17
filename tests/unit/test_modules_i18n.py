# SPDX-License-Identifier: AGPL-3.0-or-later
from whattheshell.bundled import MODULES_DIR
from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import InputSpec, OptionSpec
from whattheshell.models.module import FieldText, Translation
from whattheshell.modules.i18n import translate_command

SPEC = CommandSpec(
    name=["t"],
    summary="Original",
    description="Beschreibung",
    options=[OptionSpec(id="a", label="Alt", help="Hilfe"), OptionSpec(id="b", label="B")],
    inputs=[InputSpec(id="x", label="X")],
    subcommands=[
        CommandSpec(
            name=["t", "s"],
            summary="Sub",
            i18n={"en": Translation(summary="Sub en", inputs={"y": FieldText(label="Y en")})},
            inputs=[InputSpec(id="y", label="Y")],
        )
    ],
    i18n={
        "en": Translation(
            summary="Translated",
            options={"a": FieldText(label="Old")},
            inputs={"x": FieldText(help="X help")},
        )
    },
)


def test_translate_category() -> None:
    spec = CommandSpec(name=["t"], category="Netz", i18n={"en": Translation(category="Network")})
    assert translate_command(spec, "en").category == "Network"


def test_translate_applies_texts_recursively_on_a_copy() -> None:
    result = translate_command(SPEC, "en")
    assert result.summary == "Translated"
    assert result.description == "Beschreibung"  # untranslated field stays
    assert [(o.label, o.help) for o in result.options] == [("Old", "Hilfe"), ("B", None)]
    assert (result.inputs[0].label, result.inputs[0].help) == ("X", "X help")
    sub = result.subcommands[0]
    assert (sub.summary, sub.inputs[0].label) == ("Sub en", "Y en")
    assert SPEC.summary == "Original" and SPEC.options[0].label == "Alt"


def test_unknown_language_is_unchanged() -> None:
    assert translate_command(SPEC, "fr") == SPEC


def test_grep_module_has_english_texts() -> None:
    from whattheshell.modules.loader import load_module_file

    module = load_module_file(MODULES_DIR / "grep.module.yaml")
    spec = CommandSpec.model_validate(
        {"name": ["grep"], **module.model_dump(include={"options", "i18n"})}
    )
    ignore_case = next(o for o in translate_command(spec, "en").options if o.id == "ignore_case")
    assert ignore_case.label == "Ignore case"
