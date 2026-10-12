# SPDX-License-Identifier: AGPL-3.0-or-later
import stat
from pathlib import Path

import pytest

from whattheshell.modules.loader import DocumentError
from whattheshell.settings import Settings, load_settings, save_settings, settings_path


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "none.yaml")
    assert settings == Settings()
    assert settings.ai.enabled is False and settings.ai.send_outputs is False
    assert settings.ai.local.base_url == "http://127.0.0.1:11434/v1"
    assert settings.ai.api.key_env == "ANTHROPIC_API_KEY" and settings.ai.agent.command == []


def test_roundtrip_is_private(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "settings.yaml"
    settings = Settings()
    settings.ai.enabled = True
    settings.ai.agent.command = ["claude", "-p"]
    save_settings(settings, path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_settings(path) == settings
    assert [p.name for p in path.parent.iterdir()] == ["settings.yaml"]


def test_default_path_follows_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings_path() == tmp_path / "whattheshell" / "settings.yaml"


@pytest.mark.parametrize(
    "api",
    [
        "{api_key: abc}",
        "{key: abc}",
        "{key_env: sk-ant-1234567890}",
        "{key_env: " + "A" * 65 + "}",
        "{key_env: 1ABC}",
        "{key_env: 'MY KEY'}",
        "{key_source: file}",
    ],
)
def test_keys_in_file_are_rejected(tmp_path: Path, api: str) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text(f"schema_version: 1\nai:\n  api: {api}\n")
    with pytest.raises(DocumentError):
        load_settings(path)


def test_unknown_field_and_syntax_errors(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text("schema_version: 1\nai: {enabeld: true}\n")
    with pytest.raises(DocumentError, match="enabeld"):
        load_settings(path)
    path.write_text("ai: [")
    with pytest.raises(DocumentError):
        load_settings(path)


def test_error_does_not_echo_input(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text("schema_version: 1\nai:\n  api: {key_env: sk-geheim123}\n")
    with pytest.raises(DocumentError) as info:
        load_settings(path)
    assert "sk-geheim123" not in str(info.value)
    assert "key_env" in str(info.value)
