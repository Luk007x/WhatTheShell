# SPDX-License-Identifier: AGPL-3.0-or-later
"""``GET/PUT /api/settings``: the settings document plus the state of the key variable."""

import os
from typing import Any

from fastapi import APIRouter, Request

from whattheshell import paths
from whattheshell.api.rest import fail
from whattheshell.i18n import _, invalidate
from whattheshell.settings import Settings, save_settings

router = APIRouter(prefix="/api/settings")


def _view(settings: Settings, load_error: str | None = None) -> dict[str, Any]:
    """The document plus ``key_status`` and ``load_error`` (read-only, not part of the document).

    The key value itself is never read into the answer.
    """
    key_set = bool(os.environ.get(settings.ai.api.key_env))
    return {
        **settings.model_dump(mode="json"),
        "key_status": "set" if key_set else "missing",
        "load_error": load_error,
    }


@router.get("")
def get_settings(request: Request) -> dict[str, Any]:
    """Current settings (as loaded at start or last saved)."""
    return _view(request.app.state.settings, request.app.state.settings_error)


@router.put("")
def put_settings(request: Request, body: Settings) -> dict[str, Any]:
    """Validate (422 on errors or key fields), save atomically, reload ``app.state.settings``."""
    try:
        save_settings(body)
    except OSError as err:
        raise fail(
            500,
            "write",
            _(
                "Einstellungen nicht schreibbar: {err}. Prüfe Rechte auf {folder}.",
                err=err,
                folder=paths.config_dir(),
            ),
        ) from err
    invalidate()
    request.app.state.settings = body
    request.app.state.settings_error = None
    return _view(body)
