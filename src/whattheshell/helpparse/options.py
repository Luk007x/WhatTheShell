# SPDX-License-Identifier: AGPL-3.0-or-later
"""Parse option lines of help text into `OptionSpec` objects."""

import re
from dataclasses import dataclass, field

from whattheshell.helpparse.sections import Section, indent_of
from whattheshell.models.common import Confidence, OptionSpec, ValueType

_FLAG_RE = re.compile(r"(-{1,2}(?:\[no-\])?[A-Za-z0-9][\w.+-]*|-[#:?])(.*)", re.DOTALL)
_STOP_WORDS = frozenset(  # prose, not metavars
    {"or", "and", "is", "are", "to", "the", "a", "an", "in", "of", "for"}
    | {"with", "if", "see", "as", "by", "on", "when"}
)
_PATH_WORDS = frozenset(
    {"file", "dir", "directory", "path", "infile", "outfile", "filename", "pathname"}
)
_INT_WORDS = frozenset(
    {"num", "number", "n", "count", "lines", "levels", "seconds", "port", "bytes"}
    | {"int", "ints", "integer", "uint", "uints"}
)
_MAX_OPTION_LINE = 1000
_MULTI_METAVAR_RE = re.compile(r"(?:string|int|uint)(?:s|array|slice)")
_SIMPLE_METAVAR_RE = re.compile(r"[A-Za-z]+(?:[-_][A-Za-z]+)*\d*")
_LIST_ITEM = r"'[\w.-]+'(?:\s*\([^)]*\))?"
_QUOTED_LIST_RE = re.compile(  # "WHEN is 'always', 'never', or 'auto'"
    rf"(?:\b(?:is|are|be)|:)\s+{_LIST_ITEM}(?:(?:,\s*(?:or\s+)?|\s+or\s+){_LIST_ITEM})+"
)
_PIPE_LIST_RE = re.compile(r'\("[\w.-]+"(?:\|"[\w.-]+")+\)')  # cobra: ("a"|"b"|"c")
_WORD_LIST_RE = re.compile(
    r"(?:one of|possible values|choices|valid values|are(?=\s*:))\s*:?\s*"
    r"([a-z][\w-]*(?:\s*,\s*(?:or\s+)?[a-z][\w-]*)+)"
)
_DEFAULT_RES = (
    re.compile(r"\[default:?\s*([^\]]+)\]", re.IGNORECASE),
    re.compile(r"\(default:?\s+([^)]+)\)", re.IGNORECASE),
    re.compile(r"\bdefault:\s*(\S+)", re.IGNORECASE),
)


@dataclass
class RawOption:
    """One option as found in the text, before typing."""

    flags: list[str]
    metavar: str | None
    takes_value: bool
    indent: int
    same_line_desc: str = ""
    cont_lines: list[str] = field(default_factory=list)
    desc_col: int | None = None
    from_usage: bool = False


def split_top(text: str) -> list[str]:
    """Split on whitespace outside of ``[] <> {} ()``."""
    tokens: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char in "[<{(":
            depth += 1
        elif char in "]>})":
            depth = max(0, depth - 1)
        if char.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens if depth == 0 else text.split()


def is_path_word(word: str) -> bool:
    """Whether a metavar or argument word names a file system path (FILE, DIRS, INFILE, ...)."""
    base = word.lower().removesuffix("s")
    return base in _PATH_WORDS or (base.endswith("file") and base != "profile")


def _clean_metavar(text: str) -> str | None:
    value = text.strip().lstrip("=")
    while len(value) > 1 and value[0] + value[-1] in ("[]", "<>"):
        if value[0] == "<":  # <a|b> is a free-form placeholder, [a|b] a value list
            value = value.replace("|", "/")
        value = value[1:-1].lstrip("=")
    value = value.strip("'\"")
    return value or None


def parse_head(
    head: str, packed: bool = False, multi_meta: bool = False
) -> list[tuple[list[str], bool, str | None]] | None:
    """Parse ``-x, --long=ARG`` style text into ``(flags, takes_value, metavar)`` groups.

    Returns None if the text is not purely flags and metavars. With `packed`, every
    flag becomes its own group (find style ``-amin N -anewer FILE``).
    """
    head = re.sub(r"(?<=[\w\]>])/(?=--?[A-Za-z0-9])", " ", head)
    groups: list[tuple[list[str], bool, str | None]] = []
    meta_open = False  # last flag may still take one metavar token
    for token in split_top(head):
        token = token.rstrip(",")
        if token in ("|", ""):
            continue
        match = _FLAG_RE.fullmatch(token) if token.startswith("-") else None
        if match is None:
            if not groups or token.lower() in _STOP_WORDS or not (meta_open or multi_meta):
                return None
            flags, _, metavar = groups[-1]
            groups[-1] = (flags, True, metavar or _clean_metavar(token))
            meta_open = False
            continue
        name, rest = match.groups()
        if rest and rest[0] not in "=[<:'\"":
            return None
        names = [name]
        if "[no-]" in name:
            names = [name.replace("[no-]", ""), name.replace("[no-]", "no-")]
        if rest.startswith("[:"):  # ffmpeg stream specifier, not a value
            rest = ""
        if packed or not groups:
            groups.append(([], False, None))
        flags, value, metavar = groups[-1]
        flags.extend(names)  # in place: rebuilding the list per token is quadratic
        groups[-1] = (flags, value or bool(rest), metavar or _clean_metavar(rest))
        meta_open = not rest
    return groups or None


def _split_line(text: str) -> tuple[str, str]:
    match = re.search(r"\s{2,}", text)
    return (text[: match.start()], text[match.end() :]) if match else (text, "")


def parse_option_line(text: str) -> tuple[list[RawOption], str] | None:
    """Parse one stripped line starting with ``-`` into raw options and same-line text."""
    if len(text) > _MAX_OPTION_LINE:
        return None
    head, desc = _split_line(text)
    packed = not desc and not re.search(r"[,|]|/-", head)
    groups = parse_head(head, packed=packed, multi_meta=packed or bool(desc))
    if groups is None:
        return None
    if desc.startswith("-") and len(groups) == 1:  # gawk: "-f progfile    --file=progfile"
        extra = parse_head(desc)
        if extra is not None and len(extra) == 1:
            flags, value, metavar = groups[0]
            groups = [([*flags, *extra[0][0]], value or extra[0][1], metavar or extra[0][2])]
            desc = ""
    return [RawOption(f, m, v, 0) for f, v, m in groups], desc


def collect_options(sections: list[Section]) -> list[RawOption]:
    """Find option lines and their descriptions in all option-bearing sections."""
    found: list[RawOption] = []
    for section in sections:
        if section.kind in ("usage", "commands", "examples", "description", "name"):
            continue
        current: list[RawOption] = []
        for line in section.lines:
            if not line.strip():
                continue  # bat: "Possible values:" may follow after a blank line
            indent = indent_of(line)
            text = line.strip()
            anchor = current[-1] if current else None
            continuation = (
                anchor is not None and anchor.desc_col is not None and indent >= anchor.desc_col
            )
            parsed = parse_option_line(text) if text.startswith("-") and not continuation else None
            if parsed is not None:
                current = parsed[0]
                col = indent + len(text) - len(parsed[1]) if parsed[1] else None
                for raw in current:
                    raw.indent, raw.same_line_desc, raw.desc_col = indent, parsed[1], col
                found.extend(current)
            elif anchor is not None and indent > anchor.indent:
                for raw in current:
                    raw.cont_lines.append(text)
                    raw.desc_col = raw.desc_col if raw.desc_col is not None else indent
            else:
                current = []
    return found


def options_from_usage(usage: str) -> list[RawOption]:
    """Derive options from usage brackets such as ``[-v]``, ``[-46AaC]`` or ``[-B addr]``."""
    found: list[RawOption] = []
    depth, start = 0, 0
    for i, char in enumerate(usage):
        if char == "[":
            if depth == 0:
                start = i + 1
            depth += 1
        elif char == "]" and depth > 0:
            depth -= 1
            if depth == 0:
                inner = usage[start:i].strip()
                if inner.startswith("-"):
                    found.extend(_synopsis_group(inner))
    for raw in found:
        raw.from_usage = True
    return found


def _synopsis_group(inner: str) -> list[RawOption]:
    if re.fullmatch(r"-[A-Za-z0-9]{3,}", inner) and re.search(r"[A-Z0-9]", inner[2:]):
        return [RawOption([f"-{c}"], None, False, 0) for c in inner[1:]]
    alternatives = inner.split(" | ")
    groups = [g for alt in alternatives for g in parse_head(alt) or []]
    if len(groups) == 2 and len(alternatives) == 2:  # [-h | --help] is one option
        (f1, v1, m1), (f2, v2, m2) = groups
        if len(f1) == len(f2) == 1 and {f1[0].startswith("--"), f2[0].startswith("--")} == {
            True,
            False,
        }:
            groups = [([*f1, *f2], v1 or v2, m1 or m2)]
    return [RawOption(f, m, v, 0) for f, v, m in groups]


def iproute_options(text: str) -> list[RawOption]:
    """Options from an iproute2 ``OPTIONS := { -V[ersion] | -s[tatistics] | ... }`` block."""
    match = re.search(r"\bOPTIONS\s*:=\s*\{(.*)\}", text, re.DOTALL)
    if match is None:
        return []
    items, depth, current = [], 0, ""
    block = match.group(1)
    for char in block:
        depth += char in "[{"
        depth -= char in "]}"
        if char == "|" and depth == 0:
            items.append(current)
            current = ""
        elif depth >= 0:
            current += char
    items.append(current)
    result = []
    for item in items:
        match = re.match(r"\s*(-\w+)(?:\[(\w+)\])?\s*(.*?)\s*$", item, re.DOTALL)
        if match is None:
            continue
        flag, tail, rest = match.groups()
        flags = [flag, flag + tail] if tail else [flag]
        value = _clean_metavar(rest) if rest else None
        result.append(RawOption(flags, value, bool(rest), 0, from_usage=True))
    return result


def _derive_choices(raw: RawOption, desc: str) -> list[str]:
    meta = raw.metavar or ""
    braced = re.fullmatch(r"[\[{]?([a-z][\w-]*(?:[,|][a-z][\w-]*)+)[\]}]?", meta)
    if braced:
        return re.split(r"[,|]", braced.group(1))
    piped = _PIPE_LIST_RE.search(desc)
    if piped:
        return re.findall(r'"([\w.-]+)"', piped.group(0))
    quoted = _QUOTED_LIST_RE.search(desc)
    if quoted:
        return re.findall(r"'([\w.-]+)'", quoted.group(0))
    bullets = re.search(r"Possible values:(.*)", desc)  # bat: "* unicode (...) * caret (...)"
    if bullets:
        found = re.findall(r"(?:^|\s)\*\s+([\w-]+)", bullets.group(1))
        if found:
            return found
    words = _WORD_LIST_RE.search(desc.replace("*", ""))
    if words:
        return [w for w in re.split(r"\s*,\s*(?:or\s+)?", words.group(1)) if w]
    return []


def _derive_type(raw: RawOption, desc: str) -> tuple[ValueType, list[str], bool]:
    """Return ``(type, choices, guessed)``."""
    if not raw.takes_value:
        return ValueType.bool, [], False
    choices = _derive_choices(raw, desc)
    if choices:
        return ValueType.enum, choices, False
    meta = raw.metavar or ""
    parts = re.findall(r"[a-z]+", meta.lower()) if _SIMPLE_METAVAR_RE.fullmatch(meta) else []
    if any(is_path_word(p) for p in parts):
        return ValueType.path, [], False
    if any(p in _INT_WORDS for p in parts):
        return ValueType.int, [], False
    return ValueType.string, [], not any(p.startswith("string") for p in parts)


def _default(desc: str) -> str | None:
    for pattern in _DEFAULT_RES:
        match = pattern.search(desc)
        if match:
            value = match.group(1).strip().strip("'\"")
            if value and not value.startswith("if ") and value != "[]":
                return value
    return None


def _base_id(flags: list[str]) -> str:
    long = next((f for f in flags if f.startswith("--")), None) or next(
        (f for f in flags if len(f) > 2), None
    )
    if long:
        raw = long.lstrip("-")
    else:
        raw = flags[0].lstrip("-")
        raw += "_upper" if raw.isupper() else ""
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return slug if slug[:1].isalpha() else f"opt_{slug}".rstrip("_")


def build_options(raws: list[RawOption]) -> list[OptionSpec]:
    """Turn raw options into typed, de-duplicated, uniquely named `OptionSpec`s."""
    options: list[OptionSpec] = []
    seen_flags: set[str] = set()
    used_ids: set[str] = set()
    for raw in raws:
        if seen_flags.intersection(raw.flags):
            continue
        seen_flags.update(raw.flags)
        desc = " ".join([raw.same_line_desc, *raw.cont_lines]).strip()
        kind, choices, guessed = _derive_type(raw, desc)
        confidence = Confidence.high
        if raw.from_usage or not desc:
            confidence = Confidence.low
        elif not any(len(f) > 2 for f in raw.flags) or not raw.same_line_desc or guessed:
            confidence = Confidence.medium
        text_default = _default(desc)
        default: str | int | None = text_default
        if kind is ValueType.int and text_default is not None and text_default.isdigit():
            default = int(text_default)
        base = _base_id(raw.flags)
        option_id, n = base, 2
        while option_id in used_ids:
            option_id, n = f"{base}_{n}", n + 1
        used_ids.add(option_id)
        options.append(
            OptionSpec(
                id=option_id,
                flags=raw.flags,
                type=kind,
                choices=choices,
                default=default,
                metavar=raw.metavar,
                multiple=bool(_MULTI_METAVAR_RE.fullmatch(raw.metavar or "")),
                help=desc or None,
                confidence=confidence,
            )
        )
    return options
