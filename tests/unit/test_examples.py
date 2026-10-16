# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from whattheshell.bundled import MODULES_DIR, WORKFLOWS_DIR
from whattheshell.models.migrate import migrate
from whattheshell.models.module import Module
from whattheshell.models.workflow import Workflow


def _load(path: Path) -> dict[str, Any]:
    doc: dict[str, Any] = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    return migrate(doc)


def test_grep_module() -> None:
    Module.model_validate(_load(MODULES_DIR / "grep.module.yaml"))


def test_log_errors_workflow() -> None:
    Workflow.model_validate(_load(WORKFLOWS_DIR / "log_errors.workflow.yaml"))


@pytest.mark.parametrize("system", ["fedora", "mint"])
def test_appimage_install_workflows(system: str) -> None:
    Workflow.model_validate(_load(WORKFLOWS_DIR / f"appimage-install-{system}.workflow.yaml"))


@pytest.mark.parametrize("tool", ["test", "mkdir", "cp", "chmod", "tee"])
def test_appimage_install_modules(tool: str) -> None:
    Module.model_validate(_load(MODULES_DIR / f"{tool}.module.yaml"))
