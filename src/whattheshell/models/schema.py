# SPDX-License-Identifier: AGPL-3.0-or-later
"""JSON schema export from the models."""

import json
from pathlib import Path

from pydantic import BaseModel

from whattheshell.models.module import Module
from whattheshell.models.workflow import Workflow

SCHEMAS: dict[str, type[BaseModel]] = {"module": Module, "workflow": Workflow}


def export_schemas(out_dir: Path) -> list[Path]:
    """Write <name>.schema.json for every model.

    Args:
        out_dir: Target directory (created if missing).

    Returns:
        Written paths.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in SCHEMAS.items():
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **model.model_json_schema(),
        }
        path = out_dir / f"{name}.schema.json"
        path.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written
