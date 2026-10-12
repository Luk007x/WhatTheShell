# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest

from whattheshell.models.migrate import MigrationError, migrate


def test_missing_version() -> None:
    with pytest.raises(MigrationError, match="schema_version fehlt"):
        migrate({})


def test_newer_version() -> None:
    with pytest.raises(MigrationError, match="App aktualisieren"):
        migrate({"schema_version": 2})


def test_current_unchanged() -> None:
    doc = {"schema_version": 1, "tool": "x"}
    assert migrate(doc) == doc


@pytest.mark.parametrize("version", ["2", 0, True])
def test_invalid_version(version: object) -> None:
    with pytest.raises(MigrationError, match="ganze Zahl"):
        migrate({"schema_version": version})


@pytest.mark.parametrize("doc", [[], "text"])
def test_not_a_mapping(doc: object) -> None:
    with pytest.raises(MigrationError, match="Mapping"):
        migrate(doc)
