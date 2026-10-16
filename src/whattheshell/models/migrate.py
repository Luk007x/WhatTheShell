# SPDX-License-Identifier: AGPL-3.0-or-later
"""Schema version migration."""

from typing import Any

from whattheshell.i18n import _

CURRENT_SCHEMA_VERSION = 1


class MigrationError(ValueError):
    """Document cannot be migrated."""


def migrate(doc: object) -> dict[str, Any]:
    """Lift a document to the current schema version.

    Args:
        doc: Parsed module or workflow document.

    Returns:
        Document at CURRENT_SCHEMA_VERSION.

    Raises:
        MigrationError: Version missing or newer than this app.
    """
    if not isinstance(doc, dict):
        raise MigrationError(
            _(
                "Dokument muss ein Objekt (Mapping) sein, gefunden: {type}",
                type=type(doc).__name__,
            )
        )
    version = doc.get("schema_version")
    if version is None:
        raise MigrationError(
            _("Feld schema_version fehlt, erwartet {expected}", expected=CURRENT_SCHEMA_VERSION)
        )
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise MigrationError(
            _("schema_version muss eine ganze Zahl >= 1 sein, ist {version}", version=repr(version))
        )
    if version > CURRENT_SCHEMA_VERSION:
        raise MigrationError(
            _(
                "schema_version {version} ist neuer als unterstützt ({supported}); "
                "App aktualisieren",
                version=version,
                supported=CURRENT_SCHEMA_VERSION,
            )
        )
    return doc  # ponytail: only v1 exists, add stepwise upgrades here when v2 appears
