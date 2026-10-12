# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run the examples of the bundled modules in the real sandbox."""

from pathlib import Path

import pytest

from whattheshell.bundled import MODULES_DIR
from whattheshell.catalog.catalog import Catalog, ToolNotFound
from whattheshell.models.catalog import CommandSpec, ToolInfo
from whattheshell.models.module import Example, Fixture
from whattheshell.modules.registry import ModuleRegistry
from whattheshell.sandbox import iter_examples, run_example, self_test

STATUS = self_test()
pytestmark = pytest.mark.skipif(not STATUS.available, reason=f"Sandbox: {STATUS.reason}")


def _cases() -> list[tuple[str, str]]:
    registry = ModuleRegistry([MODULES_DIR])
    registry.scan()
    return [
        (loaded.module.tool, example.title)
        for loaded in registry.all()
        for example in loaded.module.examples
    ]


@pytest.mark.parametrize(("tool", "title"), _cases())
def test_bundled_example(tool: str, title: str, tmp_path: Path) -> None:
    registry = ModuleRegistry([MODULES_DIR])
    registry.scan()
    catalog = Catalog(cache_dir=tmp_path / "cache", registry=registry)
    try:
        info = catalog.get(tool)
    except ToolNotFound:
        pytest.skip(f"{tool} nicht installiert")
    example = next(e for i, e in iter_examples(catalog, registry, [tool]) if e.title == title)
    result = run_example(info, example, status=STATUS)
    assert result.failures == (), (
        f"{result.command}\nexit={result.exit_code}\n"
        f"stdout={result.stdout[:300]!r}\nstderr={result.stderr[:300]!r}\n"
        + "\n".join(result.failures)
    )


def test_fixture_escape_is_a_failure(tmp_path: Path) -> None:
    info = ToolInfo(
        name="true",
        path="/usr/bin/true",
        help_hash="x",
        source="fallback",
        command=CommandSpec(name=["true"]),
    )
    outside = tmp_path / "outside.txt"
    fixture = Fixture.model_construct(path=f"../{outside.name}", content="x")
    example = Example.model_construct(title="escape", fixtures=[fixture], args={}, expect=None)
    result = run_example(info, example, status=STATUS)
    assert result.failures
    assert not outside.exists()
