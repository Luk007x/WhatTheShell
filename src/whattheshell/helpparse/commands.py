# SPDX-License-Identifier: AGPL-3.0-or-later
"""Find subcommands in help text."""

import re
from collections.abc import Sequence

from whattheshell.helpparse.sections import Section, indent_of
from whattheshell.models.catalog import CommandSpec
from whattheshell.models.common import Confidence

_COMMAND_LINE_RE = re.compile(r"^(\s+)([a-z][\w.-]*):?(?:,\s*[\w.-]+)*(?:\s+(.*))?$")
_OBJECT_RE = re.compile(r"\bOBJECT\s*:=\s*\{([^}]*)\}")
_AFTER_NAME_RE = re.compile(r"^\s*(?:\[\s+)?(?:\{\s*([^}]+?)\s*\}|([a-z][\w-]*)\b)")
_WORD_RE = re.compile(r"[a-z][\w-]*")


def _make(name: Sequence[str], sub: str, summary: str | None, low: bool = False) -> CommandSpec:
    return CommandSpec(
        name=[*name, sub],
        summary=summary or None,
        confidence=Confidence.low if low else Confidence.high,
    )


def _from_sections(sections: list[Section], name: Sequence[str]) -> list[CommandSpec]:
    found: dict[str, CommandSpec] = {}
    for section in sections:
        if section.kind != "commands":
            continue
        base: int | None = None
        for line in section.lines:
            match = _COMMAND_LINE_RE.match(line)
            if match is None or (base is not None and indent_of(line) != base):
                continue
            base = indent_of(line)
            rest = (match.group(3) or "").strip()
            parts = re.split(r"\s{2,}", rest, maxsplit=1)
            summary = parts[1] if len(parts) == 2 else rest
            found.setdefault(match.group(2), _make(name, match.group(2), summary))
    return list(found.values())


def _from_object_list(text: str, name: Sequence[str]) -> list[CommandSpec]:
    match = _OBJECT_RE.search(text)
    if match is None:
        return []
    words = [w.strip() for w in match.group(1).split("|")]
    return [_make(name, w, None, low=True) for w in words if _WORD_RE.fullmatch(w)]


def _from_usage(usage: list[str], name: Sequence[str]) -> list[CommandSpec]:
    """``ip address {add|del} ...``, ``ip address del ...``, ``ip address [ show ...``."""
    found: dict[str, CommandSpec] = {}
    anchor = re.compile(rf"(?:^|\s)(?:\S*/)?{re.escape(name[-1])}\s+(.*)")
    for line in usage:
        match = anchor.search(line)
        after = _AFTER_NAME_RE.match(match.group(1)) if match else None
        if after is None:
            continue
        words = after.group(1).split("|") if after.group(1) else [after.group(2)]
        for word in (w.strip() for w in words):
            if _WORD_RE.fullmatch(word):
                found.setdefault(word, _make(name, word, None, low=True))
    return list(found.values())


def find_subcommands(sections: list[Section], text: str, name: Sequence[str]) -> list[CommandSpec]:
    """Subcommands from command sections, an iproute2 ``OBJECT := {}`` list or usage lines."""
    usage = [line for s in sections if s.kind == "usage" for line in s.lines]
    return (
        _from_sections(sections, name) or _from_object_list(text, name) or _from_usage(usage, name)
    )
