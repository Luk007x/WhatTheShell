# SPDX-License-Identifier: AGPL-3.0-or-later
"""Merge module overrides into a catalog `CommandSpec` (FORMATS section 6)."""

from collections.abc import Sequence
from typing import Any, TypeVar

from whattheshell.models.catalog import CommandSpec, unique_input_ids
from whattheshell.models.common import Confidence, InputSpec, OptionSpec
from whattheshell.models.module import CommandOverride, Module, Translation
from whattheshell.modules.registry import LoadedModule

_Spec = TypeVar("_Spec", InputSpec, OptionSpec)


def _merge_specs(base: list[_Spec], overrides: Sequence[_Spec]) -> list[_Spec]:
    """Merge by id: known id gets the set fields, unknown id is appended."""
    result = list(base)
    for item in overrides:
        update: dict[str, Any] = {name: getattr(item, name) for name in item.model_fields_set}
        update.setdefault("confidence", Confidence.high)
        index = next((i for i, spec in enumerate(result) if spec.id == item.id), None)
        if index is None:
            result.append(item.model_copy(deep=True, update=update))
        else:
            result[index] = result[index].model_copy(deep=True, update=update)
    return result


def _merge_translation(base: Translation | None, new: Translation) -> Translation:
    if base is None:
        return new.model_copy(deep=True)
    update: dict[str, Any] = {name: getattr(new, name) for name in new.model_fields_set}
    for name in ("options", "inputs"):
        update[name] = {**getattr(base, name), **getattr(new, name)}
    return base.model_copy(deep=True, update=update)


def merge_command(spec: CommandSpec, override: CommandOverride, *, replace: bool) -> CommandSpec:
    """Apply one override to a command; the inputs are not modified.

    Args:
        spec: Catalog (or already merged) command.
        override: Module or subcommand override; only its set fields count.
        replace: Discard the catalog data first (only ``raw_help`` survives).

    Returns:
        A new `CommandSpec`.
    """
    if replace:
        result = CommandSpec(name=spec.name, raw_help=spec.raw_help, confidence=Confidence.high)
    else:
        result = spec.model_copy(deep=True)
    given = override.model_fields_set
    for name in ("display_name", "category", "summary", "description", "output"):
        if name in given:
            setattr(result, name, getattr(override, name))
    if override.safety is not None:
        result.safety = override.safety
    if override.interactive is not None:
        result.interactive = override.interactive
    if "inputs" in given:  # module inputs replace the catalog ones (FORMATS section 6)
        result.inputs = _merge_specs([], override.inputs)
    result.options = _merge_specs(result.options, override.options)
    result.inputs = unique_input_ids(result.inputs, result.options)
    result.examples = [*result.examples, *(e.model_copy(deep=True) for e in override.examples)]
    if isinstance(override, Module):
        result.templates = [
            *result.templates,
            *(t.model_copy(deep=True) for t in override.templates),
        ]
    for lang, translation in override.i18n.items():
        result.i18n[lang] = _merge_translation(result.i18n.get(lang), translation)
    for sub in override.subcommands:
        existing = next((c for c in result.subcommands if c.name[-1] == sub.name), None)
        if existing is None:
            existing = CommandSpec(name=[*result.name, sub.name], confidence=Confidence.high)
            result.subcommands.append(existing)
        result.subcommands[result.subcommands.index(existing)] = merge_command(
            existing, sub, replace=False
        )
    return result


def apply_modules(spec: CommandSpec, modules: Sequence[LoadedModule]) -> CommandSpec:
    """Apply modules in the given (ascending priority) order."""
    for loaded in modules:
        spec = merge_command(spec, loaded.module, replace=loaded.module.override_mode == "replace")
    return spec
