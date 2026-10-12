# SPDX-License-Identifier: AGPL-3.0-or-later
"""Turn help text into a `CommandSpec` (never raises)."""

import logging
import re
from collections.abc import Sequence

from whattheshell.helpparse.commands import find_subcommands
from whattheshell.helpparse.options import (
    build_options,
    collect_options,
    iproute_options,
    is_path_word,
    options_from_usage,
    split_top,
)
from whattheshell.helpparse.sections import USAGE_INLINE_RE, Section, indent_of, split_sections
from whattheshell.models.catalog import CommandSpec, unique_input_ids
from whattheshell.models.common import Confidence, InputSpec, ValueType

logger = logging.getLogger(__name__)

_MAX_SUMMARY = 300
_SKIP_PLACEHOLDERS = frozenset({"option", "options", "flags", "command", "subcommand"})


def _shorten(text: str) -> str:
    """Cut at a word boundary to at most `_MAX_SUMMARY` characters, marked with an ellipsis."""
    if len(text) <= _MAX_SUMMARY:
        return text
    return text[: _MAX_SUMMARY - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _summary(sections: list[Section], name: Sequence[str]) -> str | None:
    """First prose line, or the ``NAME`` line of a man page."""
    for section in sections:
        if section.kind == "name":
            line = next((ln.strip() for ln in section.lines if ln.strip()), "")
            return line.split(" - ", 1)[-1] or None
    for section in sections:
        if section.kind in ("usage", "options", "commands"):
            continue
        for index, line in enumerate(section.lines):
            stripped = line.strip()
            if stripped.startswith("-"):
                return None  # options start here, no prose before them
            if stripped and ":=" not in stripped and stripped.split()[0] != name[-1]:
                paragraph = [stripped]
                for following in section.lines[index + 1 :]:
                    text = following.strip()
                    if not text or text.startswith("-"):
                        break
                    paragraph.append(text)
                return _shorten(" ".join(paragraph))
    return None


def _first_statement(usage_lines: list[str], name: Sequence[str]) -> str:
    """Arguments of the first usage statement (after the program name), continuations joined."""
    if not usage_lines:
        return ""
    inline = USAGE_INLINE_RE.match(usage_lines[0])
    tail = usage_lines[1:]
    if inline:
        col, parts = len(inline.group(1)), [inline.group(2)]
    elif tail:
        col, parts, tail = indent_of(tail[0]), [tail[0].strip()], tail[1:]
    else:
        return ""
    for line in tail:
        if indent_of(line) <= col:
            break
        parts.append(line.strip())
    match = re.search(rf"(?:^|\s)(?:\S*/)?{re.escape(name[-1])}(?:\s+|$)(.*)", " ".join(parts))
    return match.group(1) if match else ""


def _inputs(statement: str) -> list[InputSpec]:
    """Rough positional arguments: bare UPPERCASE, ``<x>`` and ``[x]`` tokens."""
    inputs: list[InputSpec] = []
    tokens = split_top(statement)
    for index, token in enumerate(tokens):
        multiple = token.endswith("...") or (index + 1 < len(tokens) and tokens[index + 1] == "...")
        bare = token.removesuffix("...")
        optional = bare.startswith("[")
        inner = bare.strip("[]<>")
        if not re.fullmatch(r"[A-Za-z][\w.-]*", inner):
            continue
        if not (optional or bare.startswith("<") or inner.isupper()):
            continue  # bare lowercase words are literal keywords
        slug = re.sub(r"[^a-z0-9]+", "_", inner.lower()).strip("_")
        if slug in _SKIP_PLACEHOLDERS:
            continue
        existing = next((i for i in inputs if i.id == slug), None)
        if existing is not None:
            existing.multiple = True
            continue
        inputs.append(
            InputSpec(
                id=slug,
                required=not optional,
                multiple=multiple,
                type=ValueType.path
                if any(is_path_word(w) for w in re.findall(r"[a-z]+", slug))
                else ValueType.string,
                position=len(inputs),
                metavar=inner,
                confidence=Confidence.medium,
            )
        )
    return inputs


def _parse(text: str, name: Sequence[str]) -> CommandSpec:
    sections = split_sections(text)
    usage_lines = next((s.lines for s in sections if s.kind == "usage"), [])
    usage_text = " ".join(ln.strip() for ln in usage_lines)
    raws = iproute_options(text) or collect_options(sections)
    options = build_options([*raws, *options_from_usage(usage_text)])
    subcommands = find_subcommands(sections, text, name)
    usage = USAGE_INLINE_RE.sub(r"\2", usage_lines[0]).strip() if usage_lines else None
    inputs = [] if subcommands else _inputs(_first_statement(usage_lines, name))
    inputs = unique_input_ids(inputs, options)
    return CommandSpec(
        name=list(name),
        summary=_summary(sections, name),
        usage=usage or None,
        inputs=inputs,
        options=options,
        subcommands=subcommands,
        raw_help=text,
        confidence=Confidence.high if options or subcommands else Confidence.low,
    )


def parse_help(text: str, name: Sequence[str]) -> CommandSpec:
    """Parse help text of a command into a `CommandSpec`.

    Never raises: unparsable text yields a low-confidence spec carrying only the
    summary and the raw help (the "free arguments" fallback).

    Args:
        text: Cleaned help text.
        name: Command words, e.g. ``["git", "commit"]``.
    """
    try:
        return _parse(text, name)
    except Exception:
        logger.exception("help parsing failed for %s, using fallback", list(name))
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), None)
        if first and first.lower().startswith("usage"):
            first = None
        return CommandSpec(name=list(name), summary=first, raw_help=text, confidence=Confidence.low)
