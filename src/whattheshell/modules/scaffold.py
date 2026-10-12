# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate a module skeleton from a catalog entry."""

import datetime
from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from whattheshell.models.catalog import ToolInfo
from whattheshell.models.common import Confidence, InputSpec, OptionSpec


def _field(spec: InputSpec | OptionSpec) -> CommentedMap:
    item = CommentedMap(id=spec.id)
    if isinstance(spec, OptionSpec):
        item["flags"] = list(spec.flags)
    item["type"] = spec.type.value
    for name in ("multiple", "required"):
        if getattr(spec, name):
            item[name] = True
    if spec.metavar is not None:
        item["metavar"] = spec.metavar
    if spec.choices:
        item["choices"] = list(spec.choices)
    if spec.default is not None:
        item["default"] = spec.default
    item["label"] = None
    item["group"] = None
    item["importance"] = "normal"
    item["help"] = spec.help
    if spec.confidence != Confidence.high:
        item.yaml_add_eol_comment(f"Konfidenz: {spec.confidence.value}, bitte prüfen", key="id")
    return item


def scaffold_module(info: ToolInfo) -> str:
    """Return module YAML text for a tool, ready for `load_module_file`.

    Args:
        info: Raw catalog entry (without module overrides).
    """
    command = info.command
    doc = CommentedMap()
    doc["schema_version"] = 1
    doc["tool"] = info.name
    doc["display_name"] = info.name
    doc["category"] = None
    doc["summary"] = command.summary
    doc["override_mode"] = "merge"
    doc["safety"] = command.safety.value
    doc["inputs"] = CommentedSeq(_field(i) for i in command.inputs)
    doc["options"] = CommentedSeq(_field(o) for o in command.options)
    doc["subcommands"] = [{"name": c.name[-1], "summary": c.summary} for c in command.subcommands]
    doc["output"] = {"stdout": {"kind": "lines"}, "exit_codes": {0: "Erfolg"}}
    doc["examples"] = []
    doc.yaml_set_start_comment(
        f"Modul-Gerüst für {info.name}, erzeugt aus {info.path} "
        f"({info.version or 'Version unbekannt'}) am {datetime.date.today().isoformat()}. "
        "Felder prüfen und ergänzen, siehe docs/MODULE_AUTHORING.md."
    )
    yaml = YAML(typ="rt")
    yaml.width = 100
    out = StringIO()
    yaml.dump(doc, out)
    return out.getvalue()
