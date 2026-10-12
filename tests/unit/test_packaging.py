"""Paketierung: Frontend-Build kommt ins Wheel, Build-Skript ist ausführbar."""

import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC_GLOB = "src/whattheshell/api/static/**"


def test_static_frontend_is_packaged() -> None:
    targets = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["hatch"]["build"][
        "targets"
    ]
    assert STATIC_GLOB in targets["wheel"]["artifacts"]
    assert STATIC_GLOB in targets["sdist"]["artifacts"]


def test_build_script_is_executable() -> None:
    assert os.access(ROOT / "scripts" / "build_wheel.sh", os.X_OK)
