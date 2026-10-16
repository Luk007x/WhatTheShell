# SPDX-License-Identifier: AGPL-3.0-or-later
"""User settings (``settings.yaml``); contains no secrets, only the name of a key variable."""

import re
import shlex
from io import StringIO
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import StringConstraints, field_validator, model_validator
from ruamel.yaml import YAML

from whattheshell import paths
from whattheshell.models.common import StrictModel
from whattheshell.modules.loader import load_document
from whattheshell.modules.store import atomic_write


class LocalSettings(StrictModel):
    """OpenAI-compatible local endpoint (Ollama, llama.cpp, LM Studio)."""

    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = ""
    timeout: float = 120


class ApiSettings(StrictModel):
    """Cloud API; the key itself lives in an environment variable or the keyring."""

    kind: Literal["anthropic", "openai"] = "anthropic"
    base_url: str | None = None
    model: str = ""
    key_env: str = "ANTHROPIC_API_KEY"
    key_source: Literal["env", "keyring"] = "env"
    timeout: float = 120

    @model_validator(mode="before")
    @classmethod
    def _no_key_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for name in data:
                if "key" in str(name).lower() and name not in ("key_env", "key_source"):
                    raise ValueError(
                        f"Feld '{name}' nicht erlaubt: Schlüssel gehören nie in diese Datei. "
                        "Nur der Name der Umgebungsvariable (key_env) oder key_source: keyring."
                    )
        return data

    @field_validator("key_env")
    @classmethod
    def _looks_like_name(cls, value: str) -> str:
        if len(value) > 64 or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(
                "key_env erwartet den NAMEN einer Umgebungsvariable (z. B. ANTHROPIC_API_KEY), "
                "nicht den Schlüssel selbst"
            )
        return value


# Flag -> takes a value. The only flags the app ever passes to an agent CLI; anything else
# (permission modes, tools, config overrides) could reconfigure or widen the user's agent.
AGENT_ALLOWED: dict[str, dict[str, bool]] = {
    "claude": {
        "-p": False, "--print": False, "--output-format": True, "--model": True,
        "--tools": True, "--permission-mode": True, "--no-session-persistence": False,
        "--system-prompt": True, "--strict-mcp-config": False, "--setting-sources": True,
        "--disable-slash-commands": False, "--max-turns": True,
    },
    "codex": {
        "exec": False, "--sandbox": True, "--skip-git-repo-check": False, "--ephemeral": False,
        "--ignore-user-config": False, "--ignore-rules": False, "--color": True, "-c": True,
        "-C": True, "-o": True, "-m": True, "--model": True, "-": False,
    },
}  # fmt: skip
_MODEL = r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}"
_FIXED_VALUES = {  # flag -> the only accepted values
    "--output-format": {"text"}, "--tools": {""}, "--permission-mode": {"dontAsk"},
    "--setting-sources": {""}, "--sandbox": {"read-only"}, "--color": {"never"},
    "-C": {"{tmp}"}, "-o": {"{tmp}/last.txt"},
}  # fmt: skip
# Every flag of the built-in line is required: flag -> exact value (None = bare flag or any value).
_REQUIRED: dict[str, dict[str, str | None]] = {
    "claude": {
        "-p": None, "--output-format": "text", "--tools": "", "--permission-mode": "dontAsk",
        "--no-session-persistence": None, "--system-prompt": None, "--strict-mcp-config": None,
        "--setting-sources": "", "--disable-slash-commands": None,
    },
    "codex": {
        "exec": None, "--sandbox": "read-only", "--skip-git-repo-check": None,
        "--ephemeral": None, "--ignore-user-config": None, "--ignore-rules": None,
        "--color": "never", "-C": "{tmp}", "-o": "{tmp}/last.txt", "-": None,
    },
}  # fmt: skip
_CODEX_CONFIG = {"mcp_servers": r"\{\}", "model_reasoning_effort": r'"?(low|medium|high)"?'}


def _value_error(flag: str, value: str) -> str | None:
    """Reason why `value` is not allowed for `flag`, else None."""
    if flag in _FIXED_VALUES and value not in _FIXED_VALUES[flag]:
        allowed = ", ".join(repr(v) for v in sorted(_FIXED_VALUES[flag]))
        return f"Wert {value!r} für {flag} nicht erlaubt (erlaubt: {allowed})"
    if flag in ("-m", "--model") and not re.fullmatch(_MODEL, value):
        return f"Modellname {value!r} ungültig"
    if flag == "--max-turns" and not value.isdecimal():
        return f"{flag} erwartet eine ganze Zahl"
    if flag == "-c":
        key, _, setting = value.partition("=")
        if key not in _CODEX_CONFIG or not re.fullmatch(_CODEX_CONFIG[key], setting):
            return f"-c {value!r} nicht erlaubt (Schlüssel: {', '.join(_CODEX_CONFIG)})"
    return None


def validate_command(kind: str, argv: list[str]) -> None:
    """Check the agent command line the app builds against the allowlist.

    Raises:
        ValueError: German reason naming the offending element and the allowed flags.
    """
    allowed = AGENT_ALLOWED[kind]
    hint = f"Erlaubte Flags: {' '.join(allowed)}"
    if not argv or argv[0] != kind:
        raise ValueError(f"Erstes Element muss genau `{kind}` sein. {hint}")
    if kind == "codex" and argv[1:2] != ["exec"]:
        raise ValueError(f"`exec` muss direkt auf `codex` folgen. {hint}")
    found: dict[str, str | None] = {}
    config: list[str] = []
    index = 1
    while index < len(argv):
        flag = argv[index]
        if flag not in allowed:
            raise ValueError(f"Element {flag!r} nicht erlaubt. {hint}")
        if flag in found and flag != "-c":
            raise ValueError(f"Flag {flag} doppelt. {hint}")
        value: str | None = None
        if allowed[flag]:
            if index + 1 >= len(argv):
                raise ValueError(f"{flag} braucht einen Wert. {hint}")
            value = argv[index + 1]
            problem = _value_error(flag, value)
            if problem:
                raise ValueError(f"{problem}. {hint}")
            index += 1
        if flag == "-c" and value is not None:
            config.append(value)
        found[flag] = value
        index += 1
    for flag, expected in _REQUIRED[kind].items():
        if flag not in found or (expected is not None and found[flag] != expected):
            shown = shlex.join([flag] if expected is None else [flag, expected])
            raise ValueError(f"Pflichtteil `{shown}` fehlt (hält Werkzeuge und Konfiguration aus)")
    if kind == "codex" and "mcp_servers={}" not in config:
        raise ValueError("Pflichtteil `-c mcp_servers={}` fehlt (hält MCP-Server aus)")


class AgentSettings(StrictModel):
    """Agent CLI as subprocess; the command line is built in, only model and reasoning vary."""

    kind: Literal["claude", "codex"] = "claude"
    model: Annotated[str, StringConstraints(pattern=rf"^({_MODEL})?$")] = ""
    reasoning: Literal["", "low", "medium", "high"] = ""  # codex only
    timeout: float = 300

    @model_validator(mode="before")
    @classmethod
    def _no_command(cls, data: Any) -> Any:
        if isinstance(data, dict) and "command" in data:
            raise ValueError(
                "Feld `ai.agent.command` wird nicht mehr unterstützt. "
                "Modell und Reasoning in den Einstellungen wählen."
            )
        return data


class AiSettings(StrictModel):
    """Optional AI features (F-27 to F-31); off by default."""

    enabled: bool = False
    provider: Literal["local", "api", "agent"] = "local"
    local: LocalSettings = LocalSettings()
    api: ApiSettings = ApiSettings()
    agent: AgentSettings = AgentSettings()
    send_outputs: bool = False


class Settings(StrictModel):
    """Content of ``settings.yaml``."""

    schema_version: Literal[1] = 1
    ai: AiSettings = AiSettings()


def settings_path() -> Path:
    """Return the settings file path (not created)."""
    return paths.config_dir() / "settings.yaml"


def load_settings(path: Path | None = None) -> Settings:
    """Load settings; a missing file yields the defaults.

    Raises:
        DocumentError: The file exists but is unreadable or invalid.
    """
    path = path or settings_path()
    if not path.exists():
        return Settings()
    return load_document(path, Settings, show_input=False)  # a bad value may be a key


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Write settings atomically with mode 0600.

    Raises:
        OSError: The file cannot be written.
    """
    out = StringIO()
    YAML(typ="rt").dump(settings.model_dump(mode="json"), out)
    atomic_write(path or settings_path(), out.getvalue(), 0o600)
