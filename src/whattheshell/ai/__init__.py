# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optional AI features. Importing this package must not load providers, network or process code."""

from whattheshell.settings import Settings


class AiDisabled(RuntimeError):  # noqa: N818 (name fixed by contract)
    """AI features are switched off (F-27)."""


def require_enabled(settings: Settings) -> None:
    """Gate of every AI entry point; call it before anything else.

    Raises:
        AiDisabled: ``ai.enabled`` is false.
    """
    if not settings.ai.enabled:
        raise AiDisabled(
            "KI-Funktionen sind ausgeschaltet. Einschalten mit `wts ai enable` "
            "oder in den Einstellungen."
        )
