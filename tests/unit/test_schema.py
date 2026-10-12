# SPDX-License-Identifier: AGPL-3.0-or-later
import os
from pathlib import Path

import pytest

from whattheshell.cli import main
from whattheshell.models.schema import export_schemas

COMMITTED = Path(__file__).parents[2] / "schemas"


def test_export_two_files(tmp_path: Path) -> None:
    assert sorted(p.name for p in export_schemas(tmp_path)) == [
        "module.schema.json",
        "workflow.schema.json",
    ]


def test_no_drift(tmp_path: Path) -> None:
    for fresh in export_schemas(tmp_path):
        committed = COMMITTED / fresh.name
        assert committed.read_bytes() == fresh.read_bytes(), (
            f"{fresh.name} veraltet: uv run wts schema export ausführen"
        )


def test_cli_export(tmp_path: Path) -> None:
    assert main(["schema", "export", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "module.schema.json").exists()


def test_cli_export_unwritable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        if os.access(locked, os.W_OK):
            pytest.skip("Verzeichnis trotz chmod beschreibbar (root?)")
        assert main(["schema", "export", "--out", str(locked / "out")]) == 1
    finally:
        locked.chmod(0o700)
    assert "Schemas konnten nicht geschrieben werden" in capsys.readouterr().err
