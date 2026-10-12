# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from whattheshell.models.migrate import migrate
from whattheshell.models.module import Module
from whattheshell.models.workflow import Workflow

ROOT = Path(__file__).parents[2]


def _load(path: Path) -> dict[str, Any]:
    doc: dict[str, Any] = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    return migrate(doc)


def test_grep_module() -> None:
    Module.model_validate(_load(ROOT / "modules" / "grep.module.yaml"))


def test_log_errors_workflow() -> None:
    Workflow.model_validate(_load(ROOT / "workflows" / "log_errors.workflow.yaml"))
