# SPDX-License-Identifier: AGPL-3.0-or-later
"""User settings (``settings.yaml``); contains no secrets, only the name of a key variable."""

import re
from io import StringIO
from pathlib import Path
from typing import Any, Literal

from pydantic import field_validator, model_validator
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


class AgentSettings(StrictModel):
    """Agent CLI as subprocess; empty ``command`` means the provider's default invocation."""

    kind: Literal["claude", "codex"] = "claude"
    command: list[str] = []
    timeout: float = 300


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
