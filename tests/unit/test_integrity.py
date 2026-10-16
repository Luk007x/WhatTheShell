# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import stat
from pathlib import Path

from whattheshell import bundled, integrity


def test_stamp_status_cycle(tmp_path: Path) -> None:
    file = tmp_path / "a.workflow.yaml"
    file.write_text("x: 1\n")
    assert integrity.status(file) == "unstamped"
    integrity.stamp(file)
    assert integrity.status(file) == "ok"
    file.write_text("x: 2\n")
    assert integrity.status(file) == "modified"
    integrity.stamp(file)
    assert integrity.status(file) == "ok"
    sidecar = tmp_path / integrity.SIDECAR
    assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600
    record = json.loads(sidecar.read_text())["a.workflow.yaml"]
    assert len(record["sha256"]) == 64 and record["stamped"]


def test_broken_sidecar_means_unstamped(tmp_path: Path) -> None:
    file = tmp_path / "a.workflow.yaml"
    file.write_text("x: 1\n")
    (tmp_path / integrity.SIDECAR).write_text("not json")
    assert integrity.status(file) == "unstamped"
    integrity.stamp(file)  # recovers
    assert integrity.status(file) == "ok"


def test_bundled_is_always_ok() -> None:
    first = next(bundled.WORKFLOWS_DIR.glob("*.workflow.yaml"))
    assert integrity.status(first) == "ok"


def test_path_variable_accepts_pattern() -> None:
    from whattheshell.models.workflow import VariableSpec

    assert VariableSpec.model_validate({"type": "path", "pattern": "/x.*"}).pattern == "/x.*"
