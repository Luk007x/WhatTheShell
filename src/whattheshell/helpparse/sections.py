# SPDX-License-Identifier: AGPL-3.0-or-later
"""Split help text into sections (usage, options, commands, examples, ...)."""

import re
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal[
    "preamble", "usage", "options", "commands", "examples", "description", "name", "other"
]

USAGE_INLINE_RE = re.compile(r"^(\s*usage:\s*)(\S.*)$", re.IGNORECASE)
_USAGE_ONLY = {"usage:", "usage", "synopsis"}
_OR_RE = re.compile(r"^\s*or:?\s")
_UPPER_HEADING_RE = re.compile(r"[A-Z][A-Z0-9 /&_-]{2,40}:?")


@dataclass
class Section:
    """A run of lines under one heading."""

    kind: Kind
    heading: str = ""
    lines: list[str] = field(default_factory=list)


def indent_of(line: str) -> int:
    """Number of leading spaces."""
    return len(line) - len(line.lstrip())


def _has_text(section: Section) -> bool:
    return any(line.strip() for line in section.lines)


def _heading_kind(heading: str) -> Kind:
    h = heading.lower()
    if re.search(r"option|flag", h):
        return "options"
    if "command" in h:
        return "commands"
    if "example" in h:
        return "examples"
    if "description" in h:
        return "description"
    if h.strip(": ") == "name":
        return "name"
    return "other"


def _is_heading(line: str) -> bool:
    text = line.strip()
    if indent_of(line) > 1 or text.startswith("-") or len(text) > 100:
        return False
    if text.endswith(":"):
        return True
    return indent_of(line) == 0 and bool(_UPPER_HEADING_RE.fullmatch(text))


def _usage_end(lines: list[str], start: int) -> int:
    """Index after the usage block that starts at ``lines[start]``."""
    first = lines[start]
    inline = USAGE_INLINE_RE.match(first)
    if inline is None:  # heading alone, statements follow until a blank line
        end = start + 1
        while end < len(lines) and lines[end].strip():
            end += 1
        return end
    text_col = len(inline.group(1))
    end = start + 1
    while end < len(lines) and lines[end].strip():
        if indent_of(lines[end]) < text_col and not _OR_RE.match(lines[end]):
            break
        end += 1
    return end


def split_sections(text: str) -> list[Section]:
    """Group the lines of a help text by heading.

    A usage block (``Usage:``, ``usage:``, ``SYNOPSIS``) is its own section. Text before
    the first heading is ``preamble``; text after a usage block without heading is ``other``.
    """
    lines = text.expandtabs(8).split("\n")
    sections: list[Section] = []
    current = Section("preamble")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if USAGE_INLINE_RE.match(line) or stripped.lower() in _USAGE_ONLY:
            end = _usage_end(lines, i)
            sections += [current] if _has_text(current) else []
            sections.append(Section("usage", stripped, lines[i:end]))
            current = Section("other")
            i = end
            continue
        if stripped and _is_heading(line):
            sections += [current] if _has_text(current) else []
            current = Section(_heading_kind(stripped), stripped)
        else:
            current.lines.append(line.rstrip())
        i += 1
    if _has_text(current):
        sections.append(current)
    return sections
