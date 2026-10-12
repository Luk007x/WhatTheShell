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
    assert {"gui/node_modules", "gui/tsconfig.tsbuildinfo"} <= set(targets["sdist"]["exclude"])


def test_docs_are_force_included() -> None:
    targets = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["hatch"]["build"][
        "targets"
    ]
    for name in ("MODULE_AUTHORING.md", "FORMATS.md"):
        assert (
            targets["wheel"]["force-include"][f"docs/{name}"] == f"whattheshell/bundled/docs/{name}"
        )
        assert targets["sdist"]["force-include"][f"docs/{name}"] == f"docs/{name}"


def test_build_script_is_executable() -> None:
    assert os.access(ROOT / "scripts" / "build_wheel.sh", os.X_OK)
