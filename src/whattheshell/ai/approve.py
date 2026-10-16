# SPDX-License-Identifier: AGPL-3.0-or-later
"""Approval of AI results: the only code that writes them, and only into the user's folders."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from whattheshell.ai.diff import unified
from whattheshell.i18n import _
from whattheshell.models.common import Safety
from whattheshell.models.module import Module
from whattheshell.modules.store import (
    Kind,
    user_dir,
    user_path,
    validate_module_text,
    write_user_file,
)

_RANK = {Safety.safe: 0, Safety.caution: 1, Safety.dangerous: 2}


@dataclass
class Approval:
    """A proposal waiting for the user's decision; nothing in it is ever executed."""

    kind: Literal["module", "workflow", "text"]
    target: Path | None
    old: str | None
    new: str
    diff: str
    errors: list[str] = field(default_factory=list)


def target_path(kind: Kind, target: Path) -> Path:
    """Resolve a target (relative = inside the user folder) and check it lies directly in it.

    Raises:
        ValueError: Outside the folder, in a subfolder, or a bad file name.
    """
    folder = user_dir(kind)
    parent = target.parent if target.is_absolute() else folder / target.parent
    if parent.resolve() != folder.resolve():
        raise ValueError(
            _("Ziel muss direkt in {folder} liegen, nicht {target}", folder=folder, target=target)
        )
    return user_path(kind, target.name)


def lowered_safety(old: str | None, new: str) -> list[str]:
    """Warnings for modules whose safety class (command or option) the proposal lowers."""
    before = validate_module_text(old)[0] if old else None
    after = validate_module_text(new)[0]
    if before is None or after is None:
        return []

    def classes(module: Module) -> dict[str, Safety | None]:
        found: dict[str, Safety | None] = {"": module.safety}
        found.update({_("Option {id}", id=o.id): o.safety for o in module.options})
        return found

    was, now = classes(before), classes(after)
    return [
        _(
            "ACHTUNG: Sicherheitsklasse{scope} wird von {old} auf {new} gesenkt",
            scope=_(" von {key}", key=key) if key else "",
            old=was[key],
            new=now[key],
        )
        for key in was
        if (old_class := was[key])
        and (new_class := now.get(key))
        and _RANK[new_class] < _RANK[old_class]
    ]


def propose(
    kind: Literal["module", "workflow", "text"],
    target: Path | None,
    old: str | None,
    new: str,
    errors: list[str],
) -> Approval:
    """Build an approval; the diff starts with warnings when a module lowers its safety."""
    warnings = lowered_safety(old, new) if kind == "module" else []
    diff = unified(old, new, target.name if target else _("vorschlag"))
    return Approval(
        kind, target, old, new, "\n".join([*warnings, diff]) if warnings else diff, errors
    )


def apply(approval: Approval) -> Path:
    """Write an approved proposal into the user's modules or workflows folder.

    Raises:
        ValueError: Validation errors, no target, kind ``text``, bad name or target outside the
            allowed folder.
        OSError: Not writable.
    """
    if approval.errors:
        raise ValueError(_("Vorschlag hat Validierungsfehler und wird nicht gespeichert"))
    if approval.kind == "text" or approval.target is None:
        raise ValueError(_("Nur Module und Workflows mit Zieldatei können übernommen werden"))
    target = target_path(approval.kind, approval.target)
    return write_user_file(approval.kind, target.name, approval.new)
