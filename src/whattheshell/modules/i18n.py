# SPDX-License-Identifier: AGPL-3.0-or-later
"""Apply the translations of a command spec (``i18n``) to its texts."""

from typing import TypeVar

from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import InputSpec, OptionSpec
from whattheshell.models.module import FieldText

T = TypeVar("T", InputSpec, OptionSpec)


def _fields(items: list[T], texts: dict[str, FieldText]) -> list[T]:
    result = []
    for item in items:
        text = texts.get(item.id)
        update = {} if text is None else text.model_dump(exclude_none=True)
        result.append(item.model_copy(update=update) if update else item)
    return result


def translate_command(spec: CommandSpec, lang: str) -> CommandSpec:
    """Return a copy of ``spec`` with the texts of ``spec.i18n[lang]``, recursively.

    A language without entry leaves the texts unchanged; untranslated fields keep
    their original text.
    """
    translation = spec.i18n.get(lang)
    update: dict[str, object] = {
        "subcommands": [translate_command(sub, lang) for sub in spec.subcommands]
    }
    if translation is not None:
        update |= translation.model_dump(
            exclude_none=True, include={"display_name", "summary", "description"}
        )
        update["options"] = _fields(spec.options, translation.options)
        update["inputs"] = _fields(spec.inputs, translation.inputs)
    return spec.model_copy(update=update)
