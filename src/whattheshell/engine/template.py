# SPDX-License-Identifier: AGPL-3.0-or-later
"""Render ``{{ ref }}`` templates; only plain references, no code."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

_REF = re.compile(r"(\\\{\{)|\{\{\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\}\}|(\{\{)")


class TemplateError(ValueError):
    """A template reference is malformed or unknown."""


@dataclass(frozen=True)
class StepOutput:
    """Recorded result of a finished step."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def lines(self) -> list[str]:
        """Lines of stdout without the final line break."""
        return self.stdout.removesuffix("\n").split("\n") if self.stdout else []


@dataclass(frozen=True)
class Context:
    """Everything a reference can point to."""

    variables: Mapping[str, str]
    results: Mapping[str, StepOutput]
    items: Mapping[str, str] = field(default_factory=dict)  # as-name -> value; `item` = innermost
    declared: frozenset[str] = frozenset()  # declared variable names, to explain unset ones


def resolve(ref: str, ctx: Context) -> str:
    """Resolve ``var.x``, ``<id>.stdout|stderr|exit_code|lines``, ``item`` or the foreach name.

    Raises:
        TemplateError: If the reference is unknown.
    """
    head, _, tail = ref.partition(".")
    if not tail:
        if ref in ctx.items:
            return ctx.items[ref]
        raise TemplateError(f"Unbekannte Referenz '{ref}': hier ist kein foreach-Element sichtbar")
    if head == "var":
        if tail not in ctx.variables:
            if tail in ctx.declared:
                raise TemplateError(
                    f"Variable '{tail}' hat noch keinen Wert "
                    "(wird erst durch einen Abfrage-Schritt gesetzt)."
                )
            raise TemplateError(f"Unbekannte Variable '{tail}' in '{ref}'")
        return ctx.variables[tail]
    result = ctx.results.get(head)
    if result is None:
        raise TemplateError(f"Unbekannter Schritt '{head}' in '{ref}': noch nicht gelaufen?")
    match tail:
        case "stdout" | "stderr":
            return getattr(result, tail)  # type: ignore[no-any-return]
        case "exit_code":
            return str(result.exit_code)
        case "lines":
            return "\n".join(result.lines)
    raise TemplateError(
        f"Unbekanntes Feld '{tail}' in '{ref}', erlaubt: stdout|stderr|exit_code|lines"
    )


def render(text: str, ctx: Context, *, keep_unknown: bool = False) -> str:
    """Replace all references in `text`; ``\\{{`` yields a literal ``{{``.

    Args:
        text: Template text.
        ctx: Values to resolve against.
        keep_unknown: Leave unresolvable or malformed references as written (for the plan).

    Raises:
        TemplateError: On unknown references or an unescaped, malformed ``{{``, unless
            `keep_unknown` is set.
    """

    def replace(match: re.Match[str]) -> str:
        if match.group(1):
            return "{{"
        if match.group(3):
            if keep_unknown:
                return match.group(0)
            raise TemplateError(f"Ungültiges Template in {text!r}: '{{{{' ohne gültige Referenz")
        try:
            return resolve(match.group(2), ctx)
        except TemplateError:
            if keep_unknown:
                return match.group(0)
            raise

    return _REF.sub(replace, text)


def render_value(value: object, ctx: Context, *, keep_unknown: bool = False) -> object:
    """Render strings, recurse into lists and dicts, leave anything else unchanged."""
    if isinstance(value, str):
        return render(value, ctx, keep_unknown=keep_unknown)
    if isinstance(value, list):
        return [render_value(item, ctx, keep_unknown=keep_unknown) for item in value]
    if isinstance(value, dict):
        return {
            key: render_value(item, ctx, keep_unknown=keep_unknown) for key, item in value.items()
        }
    return value
