# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

from whattheshell import paths
from whattheshell.workflows import WorkflowIndex

FLOW = "schema_version: 1\nname: {name}\nvariables:\n  v: {{}}\nsteps:\n  - {{ id: a, tool: ls }}\n"


def write(directory: Path, name: str, text: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text or FLOW.format(name=name))
    return path


def test_priority_shadows_and_errors(tmp_path: Path) -> None:
    low, mid, high = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    write(low, "x.workflow.yaml", FLOW.format(name="low"))
    write(mid, "x.workflow.yml", FLOW.format(name="mid"))
    write(high, "y.workflow.json", '{"schema_version": 1, "name": "j", "steps": []}')
    write(high, "x.workflow.yaml", FLOW.format(name="high"))
    write(low, "kaputt.workflow.yaml", "name: [")
    write(low, "ignored.txt", "")
    index = WorkflowIndex([low, mid, high])
    index.scan()
    x = index.get("x")
    assert x is not None
    assert (x.name, x.source, x.shadows) == ("high", "project", ["bundled", "user"])
    assert x.steps == 1 and "v" in x.variables
    broken = index.get("kaputt")
    assert broken is not None and broken.error and "kaputt.workflow.yaml" in broken.error
    assert {e.id for e in index.all()} == {"x", "y", "kaputt"}


def test_reload_sees_new_and_deleted_files(tmp_path: Path) -> None:
    index = WorkflowIndex([tmp_path])
    index.scan()
    assert index.all() == []
    path = write(tmp_path, "n.workflow.yaml")
    index.reload(path)
    assert index.get("n") is not None
    path.unlink()
    index.reload(path)
    assert index.get("n") is None


def test_workflow_dirs_order(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    dirs = paths.workflow_dirs(tmp_path / "proj")
    assert dirs[1] == tmp_path / "whattheshell" / "workflows"
    assert dirs[2] == tmp_path / "proj" / ".whattheshell" / "workflows"
    assert len(paths.workflow_dirs(None)) == 2
