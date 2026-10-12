# SPDX-License-Identifier: AGPL-3.0-or-later
"""Human-readable validation errors."""

from pydantic import ValidationError


def format_validation_error(
    err: ValidationError, source: str | None = None, *, show_input: bool = True
) -> str:
    """Format one line per error.

    Args:
        err: The pydantic error.
        source: Optional file name used as line prefix.
        show_input: Append the offending input; False for data that may hold secrets.

    Returns:
        Lines of the form `source: path: message (Eingabe: repr)`, the
        last part only with `show_input`.
    """
    lines = []
    for item in err.errors():
        path = ""
        for part in item["loc"]:
            path += f"[{part}]" if isinstance(part, int) else f".{part}" if path else str(part)
        prefix = f"{source}: " if source else ""
        shown = f" (Eingabe: {repr(item['input'])[:60]})" if show_input else ""
        lines.append(f"{prefix}{path or '$'}: {item['msg']}{shown}")
    return "\n".join(lines)
