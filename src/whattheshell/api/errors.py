# SPDX-License-Identifier: AGPL-3.0-or-later
"""One shape for every error answer: ``{"error", "message"[, "errors"]}``."""

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import ValidationError

from whattheshell.models.validation import format_validation_error


def error_response(
    status: int,
    error: str,
    message: str,
    errors: list[dict[str, str]] | None = None,
    **extra: Any,
) -> JSONResponse:
    """Build the JSON error answer; ``errors`` lists ``{path, message}`` entries."""
    body: dict[str, Any] = {"error": error, "message": message, **extra}
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status)


def validation_errors(err: ValidationError) -> list[dict[str, str]]:
    """One ``{path, message}`` entry per line of `format_validation_error`."""
    result = []
    for line in format_validation_error(err).splitlines():
        path, _, message = line.partition(": ")
        result.append({"path": path, "message": message})
    return result
