# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build an argv list from a command spec and field values; never a shell string."""

import shlex
from collections.abc import Mapping, Sequence

from whattheshell.i18n import _
from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import InputSpec, OptionSpec, ValueType


class ArgvError(ValueError):
    """A field value cannot be turned into command line arguments."""


def _fail(field: str, problem: str, hint: str) -> ArgvError:
    return ArgvError(
        _("Feld '{field}': {problem}. {hint}", field=field, problem=problem, hint=hint)
    )


def _convert(spec: OptionSpec | InputSpec, value: object) -> str:
    match spec.type:
        case ValueType.enum:
            if spec.choices and str(value) not in spec.choices:
                raise _fail(
                    spec.id,
                    _("Wert ist nicht erlaubt (Typ {type})", type=spec.type.value),
                    _("Erlaubt: {choices}", choices=", ".join(spec.choices)),
                )
        case ValueType.int | ValueType.float:
            number = int if spec.type is ValueType.int else float
            try:
                number(str(value))
            except ValueError:
                raise _fail(
                    spec.id,
                    _("Wert ist keine Zahl"),
                    _("Erwartet: {type}", type=spec.type.value),
                ) from None
    return str(value)


def _as_bool(spec: OptionSpec, value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value in ("true", "false"):
        return value == "true"
    raise _fail(
        spec.id,
        _("Wert ist kein Wahrheitswert (Typ bool)"),
        _("Erwartet: true oder false"),
    )


def _as_list(spec: OptionSpec | InputSpec, value: object) -> list[object]:
    if not isinstance(value, list):
        raise _fail(spec.id, _("erwartet eine Liste"), _("Mehrfachfeld als Liste angeben"))
    return value


def _option_argv(option: OptionSpec, value: object) -> list[str]:
    if not option.flags:
        raise _fail(option.id, _("Option hat kein Flag"), _("Modul oder Katalog prüfen"))
    flag = next((f for f in option.flags if f.startswith("--")), option.flags[0])
    if option.type is ValueType.bool:
        return [flag] if _as_bool(option, value) else []
    if not option.multiple and option.nargs == 1 and isinstance(value, list):
        raise ArgvError(
            _(
                "Option '{id}' erwartet einen einzelnen Wert, bekam Liste. Einzelwert angeben",
                id=option.id,
            )
        )
    argv: list[str] = []
    for occurrence in _as_list(option, value) if option.multiple else [value]:
        if option.nargs > 1:
            parts = _as_list(option, occurrence)
            if len(parts) != option.nargs:
                raise _fail(
                    option.id,
                    _(
                        "erwartet {expected} Werte je Vorkommen, erhalten {got}",
                        expected=option.nargs,
                        got=len(parts),
                    ),
                    _("Liste mit passender Länge angeben"),
                )
            argv += [flag, *(_convert(option, part) for part in parts)]
        elif option.attached and flag.startswith("--"):
            argv.append(f"{flag}={_convert(option, occurrence)}")
        else:
            argv += [flag, _convert(option, occurrence)]
    return argv


def _input_argv(spec: InputSpec, value: object) -> list[str]:
    if value is None:
        if spec.required:
            raise _fail(spec.id, _("Pflichteingabe fehlt"), _("Wert angeben"))
        return []
    values = _as_list(spec, value) if spec.multiple else [value]
    return [_convert(spec, item) for item in values]


def build_argv(
    spec: CommandSpec,
    args: Mapping[str, object],
    extra_args: Sequence[str] = (),
    *,
    tool_path: str | None = None,
) -> list[str]:
    """Build the argv list: tool, subcommand, before-options inputs, options, inputs, extra args.

    Args:
        spec: The (sub)command to run.
        args: Field values by option or input id; None means unset.
        extra_args: Appended unchanged.
        tool_path: Executable to use instead of ``spec.name[0]``.

    Raises:
        ArgvError: Unknown field, missing required input or invalid value.
    """
    known = [item.id for item in (*spec.options, *spec.inputs)]
    for key in args:
        if key not in known:
            raise ArgvError(
                _(
                    "Unbekanntes Feld '{key}' für {tool}, bekannte Felder: {known}",
                    key=key,
                    tool=spec.name[0],
                    known=", ".join(sorted(known)),
                )
            )
    argv = [tool_path or spec.name[0], *spec.name[1:]]
    ordered = sorted(
        enumerate(spec.inputs),
        key=lambda pair: pair[0] if pair[1].position is None else pair[1].position,
    )
    for _index, positional in ordered:
        if positional.before_options:
            argv += _input_argv(positional, args.get(positional.id))
    for option in spec.options:
        if args.get(option.id) is not None:
            argv += _option_argv(option, args[option.id])
    for _index, positional in ordered:
        if not positional.before_options:
            argv += _input_argv(positional, args.get(positional.id))
    return [*argv, *extra_args]


def display(argv: Sequence[str]) -> str:
    """Quote an argv list for display only."""
    return shlex.join(argv)
