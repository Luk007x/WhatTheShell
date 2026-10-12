# SPDX-License-Identifier: AGPL-3.0-or-later
"""Schema version migration."""

from typing import Any

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
            f"Dokument muss ein Objekt (Mapping) sein, gefunden: {type(doc).__name__}"
        )
    version = doc.get("schema_version")
    if version is None:
        raise MigrationError(f"Feld schema_version fehlt, erwartet {CURRENT_SCHEMA_VERSION}")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise MigrationError(f"schema_version muss eine ganze Zahl >= 1 sein, ist {version!r}")
    if version > CURRENT_SCHEMA_VERSION:
        raise MigrationError(
            f"schema_version {version} ist neuer als unterstützt "
            f"({CURRENT_SCHEMA_VERSION}); App aktualisieren"
        )
    return doc  # ponytail: only v1 exists, add stepwise upgrades here when v2 appears
