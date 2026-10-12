# SPDX-License-Identifier: AGPL-3.0-or-later
"""Human-readable validation errors."""

from pydantic import ValidationError


def format_validation_error(err: ValidationError, source: str | None = None) -> str:
    """Format one line per error.

    Args:
        err: The pydantic error.
        source: Optional file name used as line prefix.

    Returns:
        Lines of the form `source: path: message (Eingabe: repr)`.
    """
    lines = []
    for item in err.errors():
        path = ""
        for part in item["loc"]:
            path += f"[{part}]" if isinstance(part, int) else f".{part}" if path else str(part)
        prefix = f"{source}: " if source else ""
        shown = repr(item["input"])[:60]
        lines.append(f"{prefix}{path or '$'}: {item['msg']} (Eingabe: {shown})")
    return "\n".join(lines)
