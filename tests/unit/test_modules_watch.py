# SPDX-License-Identifier: AGPL-3.0-or-later
import threading
import time
from collections.abc import Callable
from pathlib import Path

from whattheshell.modules.registry import ModuleRegistry
from whattheshell.modules.watch import watch_modules


def wait_for(condition: Callable[[], bool]) -> bool:
    for _ in range(50):
        if condition():
            return True
        time.sleep(0.1)
    return False


def test_no_dirs_returns_immediately() -> None:
    watch_modules(ModuleRegistry([]), threading.Event())


def test_watch_missing_dir_then_created(tmp_path: Path) -> None:
    target = tmp_path / "nicht" / "vorhanden"
    registry = ModuleRegistry([target])
    stop = threading.Event()
    started: list[list[tuple[Path, Path]]] = []
    thread = threading.Thread(
        target=watch_modules, args=(registry, stop, None, started.append), daemon=True
    )
    thread.start()
    assert wait_for(lambda: bool(started))
    assert started[0] == [(target.resolve(), tmp_path.resolve())]
    time.sleep(0.5)
    target.mkdir(parents=True)
    time.sleep(0.5)
    (target / "demo.module.yaml").write_text("schema_version: 1\ntool: demo\n", encoding="utf-8")
    assert wait_for(lambda: bool(registry.for_tool("demo")))
    stop.set()
    thread.join(timeout=5)


def test_watch_reload(tmp_path: Path) -> None:
    registry = ModuleRegistry([tmp_path])
    stop = threading.Event()
    seen: list[set[Path]] = []
    thread = threading.Thread(target=watch_modules, args=(registry, stop, seen.append), daemon=True)
    thread.start()
    time.sleep(0.5)  # let the watcher arm
    path = tmp_path / "demo.module.yaml"
    path.write_text("schema_version: 1\ntool: demo\n", encoding="utf-8")
    assert wait_for(lambda: bool(registry.for_tool("demo")))
    path.write_text("schema_version: 1\ntool: [\n", encoding="utf-8")
    assert wait_for(lambda: bool(registry.errors))
    assert seen
    stop.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
