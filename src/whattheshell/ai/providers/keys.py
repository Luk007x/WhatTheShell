# SPDX-License-Identifier: AGPL-3.0-or-later
"""API key lookup; the key is never logged or put into an error message."""

import logging
import os

from whattheshell.i18n import _
from whattheshell.settings import ApiSettings

logger = logging.getLogger(__name__)


def resolve_key(api: ApiSettings) -> str:
    """Return the key from the environment variable or the keyring.

    Raises:
        RuntimeError: Variable unset, keyring missing, or no entry stored.
    """
    if api.key_source == "env":
        try:
            return os.environ[api.key_env]
        except KeyError:
            raise RuntimeError(
                _(
                    "Umgebungsvariable {name} nicht gesetzt: "
                    "`export {name}=…` oder key_source auf keyring stellen",
                    name=api.key_env,
                )
            ) from None
    try:
        import keyring  # type: ignore[import-not-found,unused-ignore]  # optional extra
    except ImportError:
        raise RuntimeError(
            _("Schlüsselbund-Unterstützung nicht installiert: `pipx inject whattheshell keyring`")
        ) from None
    try:
        key: str | None = keyring.get_password("whattheshell", api.key_env)
    except Exception as err:  # any backend error (locked, no D-Bus, …); message may be unsafe
        logger.warning("Schlüsselbund-Fehler: %s", type(err).__name__)
        raise RuntimeError(
            _(
                "Schlüsselbund nicht lesbar ({error}): entsperren oder key_source auf env stellen",
                error=type(err).__name__,
            )
        ) from None
    if key is None:
        raise RuntimeError(
            _(
                "Kein Schlüssel '{name}' im Schlüsselbund (Dienst 'whattheshell') gefunden",
                name=api.key_env,
            )
        )
    return key
