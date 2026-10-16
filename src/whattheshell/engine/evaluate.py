# SPDX-License-Identifier: AGPL-3.0-or-later
"""Evaluate workflow conditions."""

import json
import re
from pathlib import Path
from typing import Any

from whattheshell.engine.template import Context, TemplateError, resolve
from whattheshell.i18n import _
from whattheshell.models.workflow import Condition
from whattheshell.paths import inside

_NUMBER = re.compile(r"-?\d+(\.\d+)?")
_JSON_SEGMENT = re.compile(r"\.?([^.\[\]]+)|\[(\d+)\]")


class EvalError(ValueError):
    """A condition cannot be evaluated."""


def _inside(path: str, cwd: Path) -> Path:
    target = cwd / path
    if not inside(target, cwd):
        raise EvalError(_("Pfad '{path}' liegt außerhalb des Arbeitsverzeichnisses", path=path))
    return target.resolve()


def _source_text(source: str, ctx: Context, cwd: Path, *, missing_ok: bool) -> str:
    if source.startswith("file:"):
        target = _inside(source.removeprefix("file:"), cwd)
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            if missing_ok:
                return ""
            raise EvalError(
                _("Datei '{file}' aus '{source}' existiert nicht", file=target, source=source)
            ) from None
        except OSError as err:
            raise EvalError(_("Datei '{file}' nicht lesbar: {err}", file=target, err=err)) from err
    try:
        return resolve(source, ctx)
    except TemplateError as err:
        raise EvalError(str(err)) from err


def _number(text: str, source: str) -> float:
    match = _NUMBER.search(text)
    if match is None:
        raise EvalError(_("Keine Zahl in '{source}' gefunden", source=source))
    return float(match.group())


def _json_present(text: str, path: str, source: str) -> bool:
    try:
        node = json.loads(text)
    except json.JSONDecodeError as err:
        raise EvalError(
            _("'{source}' ist kein gültiges JSON: {err}", source=source, err=err)
        ) from err
    for match in _JSON_SEGMENT.finditer(path):
        key, index = match.groups()
        if index is not None:
            if not isinstance(node, list) or int(index) >= len(node):
                return False
            node = node[int(index)]
        elif isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return False
    return node is not None


def _equals(text: str, operand: str | int | float | bool) -> bool:
    text = text.rstrip("\n")
    if isinstance(operand, bool):
        return text.strip().lower() == str(operand).lower()
    if isinstance(operand, int | float):
        match = _NUMBER.fullmatch(text.strip())
        return match is not None and float(text) == operand
    return text == operand


def _check(cond: Condition, ctx: Context, *, cwd: Path) -> Any:
    operator = cond.operator
    operand = getattr(cond, operator)
    if operator == "file_exists":
        raw = cond.source.removeprefix("file:") if cond.source.startswith("file:") else None
        path = (
            raw
            if raw is not None
            else _source_text(cond.source, ctx, cwd, missing_ok=False).strip()
        )
        return _inside(path, cwd).exists() == operand
    text = _source_text(cond.source, ctx, cwd, missing_ok=False)
    match operator:
        case "eq":
            return _equals(text, operand)
        case "ne":
            return not _equals(text, operand)
        case "contains":
            return operand in text
        case "regex":
            return re.search(operand, text) is not None
        case "is_empty":
            return (not text.strip()) == operand
        case "line_count_gt" | "line_count_eq":
            count = len(text.rstrip().splitlines())
            return count > operand if operator.endswith("gt") else count == operand
        case "number_gt":
            return _number(text, cond.source) > operand
        case "number_lt":
            return _number(text, cond.source) < operand
        case "number_eq":
            return _number(text, cond.source) == operand
        case _:  # json_path
            return _json_present(text, operand, cond.source)


def evaluate(cond: Condition, ctx: Context, *, cwd: Path) -> bool:
    """Evaluate a condition against the context.

    Raises:
        EvalError: Unknown reference, unreadable file, missing number or invalid JSON.
    """
    return bool(_check(cond, ctx, cwd=cwd))
