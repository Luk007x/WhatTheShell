# SPDX-License-Identifier: AGPL-3.0-or-later
"""Modules and workflows shipped with the package (data files, CC0-1.0)."""

from pathlib import Path

MODULES_DIR = Path(__file__).parent / "modules"
WORKFLOWS_DIR = Path(__file__).parent / "workflows"
# filled at build time by hatch force-include (see pyproject.toml); absent in a source checkout
DOCS_DIR = Path(__file__).parent / "docs"
