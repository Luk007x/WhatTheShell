# SPDX-License-Identifier: AGPL-3.0-or-later
"""PATH scan and lazily built, disk-cached tool catalog."""

import hashlib
import json
import logging
import os
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from whattheshell import paths
from whattheshell.catalog.fetch import NEVER_PROBE, fetch_help
from whattheshell.helpparse import parse_help
from whattheshell.models.catalog import CommandSpec, ToolInfo
from whattheshell.models.common import Confidence
from whattheshell.subproc import run_limited

logger = logging.getLogger(__name__)

INTERACTIVE = frozenset(
    {
        "vi",
        "vim",
        "nvim",
        "emacs",
        "nano",
        "pico",
        "less",
        "more",
        "most",
        "top",
        "htop",
        "btop",
        "ssh",
        "telnet",
        "ftp",
        "sftp",
        "tmux",
        "screen",
        "python",
        "python3",
        "ipython",
        "node",
        "irb",
        "bash",
        "sh",
        "zsh",
        "fish",
        "mc",
        "ranger",
        "nmtui",
        "alsamixer",
        "cmus",
        "mutt",
        "lynx",
        "w3m",
    }
)
_MAX_SUBCOMMANDS = 40
_VERSION_TIMEOUT = 3.0


class ToolNotFound(LookupError):  # noqa: N818 (name fixed by contract)
    """The requested tool is not on PATH."""


@dataclass(frozen=True)
class Executable:
    """An executable file found on PATH."""

    name: str
    path: str


def scan_path(path: str | None = None) -> list[Executable]:
    """List executables on PATH, first hit per name wins, sorted by name.

    Args:
        path: PATH-style string; defaults to ``os.environ["PATH"]``.
    """
    found: dict[str, Executable] = {}
    for directory in (os.environ.get("PATH", "") if path is None else path).split(os.pathsep):
        if not directory:
            continue
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name)
        except OSError:
            continue  # missing or unreadable directory
        for entry in entries:
            if entry.name not in found and entry.is_file() and os.access(entry.path, os.X_OK):
                found[entry.name] = Executable(entry.name, entry.path)
    return sorted(found.values(), key=lambda e: e.name)


def _probe_version(path: str) -> str | None:
    done = run_limited([path, "--version"], timeout=_VERSION_TIMEOUT, max_bytes=4096)
    if done is None:
        return None
    lines = (done.stdout or done.stderr).decode("utf-8", errors="replace").strip().splitlines()
    return lines[0].strip()[:200] if lines else None


class Catalog:
    """Resolves tools and builds `ToolInfo` entries with an on-disk cache."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or paths.cache_dir() / "catalog"
        self._tools: list[Executable] | None = None

    def tools(self) -> list[Executable]:
        """All executables on PATH (scanned once per instance)."""
        if self._tools is None:
            self._tools = scan_path()
        return self._tools

    def _resolve(self, name: str) -> str:
        if "/" in name:
            found = name if os.access(name, os.X_OK) and os.path.isfile(name) else None
        else:
            found = shutil.which(name)
        if found is None:
            raise ToolNotFound(
                f"Tool '{name}' nicht auf PATH gefunden. Prüfe die Schreibweise "
                "oder installiere es."
            )
        return found

    def get(
        self,
        name: str,
        subcommand: Sequence[str] = (),
        *,
        refresh: bool = False,
        depth: int = 0,
    ) -> ToolInfo:
        """Return the catalog entry of a tool or subcommand.

        Args:
            name: Tool name or path (containing ``/``).
            subcommand: Subcommand words.
            refresh: Ignore a valid cache entry.
            depth: Levels of subcommands to resolve as well.

        Raises:
            ToolNotFound: The tool cannot be found or executed.
        """
        path = self._resolve(name)
        base = os.path.basename(path)
        stat = os.stat(path)
        key = {"path": path, "mtime_ns": stat.st_mtime_ns, "size": stat.st_size}
        cache_file = self._cache_dir / (".".join([base, *subcommand]).replace("/", "_") + ".json")
        info = None if refresh else self._read(cache_file, key)
        if info is None:
            info = self._build(path, base, subcommand)
            self._write(cache_file, key, info)
        if depth > 0:
            info = self._expand(info, name, subcommand, depth)
        return info

    def _read(self, cache_file: Path, key: dict[str, object]) -> ToolInfo | None:
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if any(data.get(k) != v for k, v in key.items()):
                return None
            return ToolInfo.model_validate(data["info"])
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, AttributeError, ValidationError) as err:
            logger.warning("Cache %s unbrauchbar, wird neu erzeugt: %s", cache_file, err)
            return None

    def _write(self, cache_file: Path, key: dict[str, object], info: ToolInfo) -> None:
        payload = {**key, "info": info.model_dump(mode="json")}
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=cache_file.parent, suffix=".tmp", delete=False
            ) as tmp:
                json.dump(payload, tmp)
            os.replace(tmp.name, cache_file)
        except OSError as err:
            logger.warning(
                "Cache %s nicht beschreibbar (%s). Prüfe die Rechte von %s.",
                cache_file,
                err,
                self._cache_dir,
            )

    def _build(self, path: str, base: str, subcommand: Sequence[str]) -> ToolInfo:
        words = [base, *subcommand]
        help_text = fetch_help(path, subcommand)
        if help_text is None:
            command = CommandSpec(name=words, raw_help="", confidence=Confidence.low)
            source: Literal["help", "man", "fallback"] = "fallback"
            digest = hashlib.sha256(b"").hexdigest()
        else:
            command = parse_help(help_text.text, words)
            source = "man" if help_text.source == "man" else "help"
            digest = hashlib.sha256(help_text.text.encode()).hexdigest()
        command.interactive = base in INTERACTIVE
        version = None if subcommand or base in NEVER_PROBE else _probe_version(path)
        return ToolInfo(
            name=base,
            path=path,
            version=version,
            help_hash=digest,
            source=source,
            command=command,
        )

    def _expand(self, info: ToolInfo, name: str, subcommand: Sequence[str], depth: int) -> ToolInfo:
        expanded = info.model_copy(deep=True)
        subs = sorted(expanded.command.subcommands, key=lambda c: c.name[-1])[:_MAX_SUBCOMMANDS]
        for index, sub in enumerate(subs):
            try:
                child = self.get(name, (*subcommand, sub.name[-1]), depth=depth - 1)
            except (LookupError, OSError) as err:
                logger.warning("Subbefehl %s nicht lesbar: %s", sub.name, err)
                continue
            if child.source != "fallback":
                subs[index] = child.command
        expanded.command.subcommands = subs
        return expanded
