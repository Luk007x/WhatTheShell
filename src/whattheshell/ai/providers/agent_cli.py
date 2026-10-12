# SPDX-License-Identifier: AGPL-3.0-or-later
"""Agent CLIs (Claude Code, Codex) as limited subprocess with a throwaway HOME (D-011, D-012)."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from whattheshell.ai.protocol import Prompt
from whattheshell.ai.providers.http import printable
from whattheshell.subproc import run_limited, sanitized_env

_MAX_BYTES = 2 * 1024 * 1024
_PROXY_VARS = tuple(v for n in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY") for v in (n, n.lower()))
_KEY_VARS = {"claude": "ANTHROPIC_API_KEY", "codex": "CODEX_API_KEY"}
# Only the login file enters the temp HOME: no CLAUDE.md, settings, hooks, plugins, config.toml.
CREDENTIALS = {"claude": ".claude/.credentials.json", "codex": ".codex/auth.json"}


def _default_command(kind: str) -> list[str]:
    if kind == "claude":
        return [
            "claude", "-p", "--output-format", "text", "--tools", "",
            "--permission-mode", "dontAsk", "--no-session-persistence",
            "--system-prompt", "{system}",
            "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
        ]  # fmt: skip
    return [
        "codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral",
        "--ignore-user-config", "--ignore-rules",
        "--color", "never", "-c", "mcp_servers={}", "-C", "{tmp}", "-o", "{tmp}/last.txt", "-",
    ]  # fmt: skip


@contextmanager
def isolated_env(kind: Literal["claude", "codex"]) -> Iterator[tuple[dict[str, str], Path]]:
    """Temp dir with ``home/`` (login file only, 0600) and ``work/``; removed on exit.

    Yields:
        The environment for the agent (``HOME`` and XDG dirs inside the temp dir, key and proxy
        variables passed through) and the empty working directory.

    Raises:
        OSError: The login file exists but cannot be copied.
    """
    with tempfile.TemporaryDirectory(prefix="wts-agent-") as tmp:  # 0700, deleted in finally
        home, work = Path(tmp, "home"), Path(tmp, "work")
        work.mkdir()
        source = Path.home() / CREDENTIALS[kind]  # resolved from the real HOME
        target = home / CREDENTIALS[kind]
        target.parent.mkdir(parents=True)
        if source.is_file():
            shutil.copyfile(source, target)
            target.chmod(0o600)
        env = sanitized_env()
        for var in (_KEY_VARS[kind], *_PROXY_VARS):
            if var in os.environ:
                env[var] = os.environ[var]
        env |= {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
        }
        yield env, work


class AgentCliProvider:
    """Runs the agent with the prompt on stdin; the answer is untrusted text."""

    def __init__(
        self,
        kind: Literal["claude", "codex"],
        command: list[str],
        timeout: float,
    ) -> None:
        self.name: str = kind
        self._kind = kind
        self._command = command or _default_command(kind)
        self._timeout = timeout

    def complete(self, prompt: Prompt) -> str:
        """Run the CLI in a throwaway HOME and return its answer.

        Raises:
            RuntimeError: Program missing, timeout, or non-zero exit.
            OSError: The login file cannot be copied into the temp HOME.
        """
        with isolated_env(self._kind) as (env, work):
            argv = [
                part.replace("{system}", prompt.system).replace("{tmp}", str(work))
                for part in self._command
            ]
            stdin = prompt.user
            if not any("{system}" in part for part in self._command):
                stdin = f"{prompt.system}\n\n{prompt.user}"
            result = run_limited(
                argv, timeout=self._timeout, max_bytes=_MAX_BYTES, env=env, cwd=str(work),
                stdin=stdin.encode(),
            )  # fmt: skip
            program = argv[0]
            if result is None:
                raise RuntimeError(f"Programm `{program}` nicht gefunden")
            if result.timed_out:
                raise RuntimeError(
                    f"`{program}` hat das Zeitlimit von {self._timeout:g} s überschritten"
                )
            if result.truncated:
                raise RuntimeError(f"Antwort von `{program}` über dem Limit abgeschnitten")
            if result.exit_code != 0:
                detail = printable(result.stderr.decode(errors="replace").strip()[:300])
                raise RuntimeError(f"`{program}` endete mit Code {result.exit_code}: {detail}")
            last = work / "last.txt"
            if self._kind == "codex" and last.exists():
                with last.open("rb") as handle:
                    data = handle.read(_MAX_BYTES + 1)
                if len(data) > _MAX_BYTES:
                    raise RuntimeError(f"Antwort von `{program}` über dem Limit abgeschnitten")
                return data.decode(errors="replace")
            return result.stdout.decode(errors="replace")
