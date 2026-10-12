# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

from whattheshell.models.catalog import CommandSpec, ToolInfo
from whattheshell.models.common import Confidence, OptionSpec, ValueType
from whattheshell.modules.loader import load_module_file
from whattheshell.modules.scaffold import scaffold_module


def test_scaffold_validates(tmp_path: Path) -> None:
    command = CommandSpec(
        name=["demo"],
        summary="Does: things",
        options=[
            OptionSpec(id="a", flags=["-a"], help="flag"),
            OptionSpec(
                id="n",
                flags=["-n"],
                type=ValueType.int,
                metavar="N",
                default=3,
                confidence=Confidence.medium,
            ),
        ],
        subcommands=[CommandSpec(name=["demo", "sub"], summary="s")],
    )
    text = scaffold_module(
        ToolInfo(name="demo", path="/bin/demo", help_hash="x", source="help", command=command)
    )
    assert text.startswith("# Modul-Gerüst für demo, erzeugt aus /bin/demo (Version unbekannt)")
    assert "# Konfidenz: medium, bitte prüfen" in text
    path = tmp_path / "demo.module.yaml"
    path.write_text(text, encoding="utf-8")
    module = load_module_file(path)
    assert module.tool == "demo"
    assert len(module.options) == 2
    assert module.subcommands[0].name == "sub"
