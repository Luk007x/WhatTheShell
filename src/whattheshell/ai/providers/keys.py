# SPDX-License-Identifier: AGPL-3.0-or-later
"""API key lookup; the key is never logged or put into an error message."""

import os

from whattheshell.settings import ApiSettings


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
                f"Umgebungsvariable {api.key_env} nicht gesetzt: "
                f"`export {api.key_env}=…` oder key_source auf keyring stellen"
            ) from None
    try:
        import keyring  # type: ignore[import-not-found,unused-ignore]  # optional extra
    except ImportError:
        raise RuntimeError(
            "Schlüsselbund-Unterstützung nicht installiert: `pipx inject whattheshell keyring`"
        ) from None
    key: str | None = keyring.get_password("whattheshell", api.key_env)
    if key is None:
        raise RuntimeError(
            f"Kein Schlüssel '{api.key_env}' im Schlüsselbund (Dienst 'whattheshell') gefunden"
        )
    return key
