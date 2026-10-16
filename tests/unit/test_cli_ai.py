# SPDX-License-Identifier: AGPL-3.0-or-later
import io
import json
import socket
import subprocess
from pathlib import Path

import pytest

from whattheshell import cli
from whattheshell.ai.fake import FakeProvider
from whattheshell.cli import main
from whattheshell.settings import load_settings, settings_path

from .test_engine_runner import tools  # noqa: F401

pytestmark = pytest.mark.usefixtures("tools")

MODULE = "schema_version: 1\ntool: echo-args\ndisplay_name: Echo\nsummary: Zeigt Argumente\n"
WORKFLOW = "schema_version: 1\nname: Mein Test\nsteps:\n  - { id: a, kind: message, text: hi }\n"
KEY = "sk-ant-TOPSECRET-1234"


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider([])
    monkeypatch.setattr(cli, "make_provider", lambda settings: provider)
    return provider


def _enable() -> None:
    assert main(["ai", "enable"]) == 0


def _modules(tmp_path: Path) -> Path:
    return tmp_path / "xdg-config" / "whattheshell" / "modules"


def test_enable_disable_status(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["ai", "status"]) == 0
    out = capsys.readouterr().out
    assert "KI: aus" in out and "ENV ANTHROPIC_API_KEY (nicht gesetzt)" in out
    _enable()
    assert load_settings().ai.enabled and settings_path().exists()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    main(["ai", "status"])
    out = capsys.readouterr().out
    assert "KI: an" in out and "ENV ANTHROPIC_API_KEY (gesetzt)" in out and KEY not in out
    assert main(["ai", "disable"]) == 0
    assert not load_settings().ai.enabled


def test_check_and_status_summary(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ai", "check"]) == 1
    out = capsys.readouterr().out
    assert "KI aus" in out and "wts ai enable" in out and "nicht bereit" in out
    _enable()
    assert main(["ai", "config", "set", "local.model", "llama3"]) == 0
    assert main(["ai", "check", "--no-network"]) == 0
    out = capsys.readouterr().out
    assert "Modell eingetragen: llama3" in out and "KI-Quelle 'local': bereit" in out


def test_status_starts_no_process_and_opens_no_connection(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    assert main(["ai", "config", "set", "provider", "agent"]) == 0

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Prozess oder Verbindung bei `wts ai status`")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert main(["ai", "status"]) == 0
    assert "wts ai check" in capsys.readouterr().out


def test_improve_module_prompt_for_wc_is_short(fake: FakeProvider) -> None:
    _enable()
    fake._responses.append("schema_version: 1\ntool: wc\n")
    main(["ai", "improve-module", "wc", "--yes"])
    prompt = fake.prompts[0]
    assert len(f"{prompt.system}\n{prompt.user}".splitlines()) < 200
    assert "Modulautorenhandbuch" not in prompt.system + prompt.user


def test_config_set(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ai", "config", "set", "provider", "agent"]) == 0
    assert main(["ai", "config", "set", "agent.kind", "codex"]) == 0
    assert main(["ai", "config", "set", "api.model", "claude-x"]) == 0
    assert main(["ai", "config", "set", "send_outputs", "true"]) == 0
    assert main(["ai", "config", "set", "agent.model", "gpt-x"]) == 0
    ai = load_settings().ai
    assert (ai.provider, ai.agent.kind, ai.api.model) == ("agent", "codex", "claude-x")
    assert ai.send_outputs is True and ai.agent.model == "gpt-x"
    capsys.readouterr()
    assert main(["ai", "config", "set", "provider", "cloud"]) == 1
    assert main(["ai", "config", "set", "api.api_key", "abc"]) == 1
    assert main(["ai", "config", "set", "provider.x", "abc"]) == 1
    assert main(["ai", "config", "set", "api.key_env", KEY]) == 1
    assert KEY not in capsys.readouterr().err
    assert load_settings().ai.provider == "agent"


def test_improve_module_yes_writes_valid_module(
    tmp_path: Path, fake: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    fake._responses.append(f"Gern, hier:\n```yaml\n{MODULE}```\n")
    assert main(["ai", "improve-module", "echo-args", "--yes", "--apply"]) == 0
    path = _modules(tmp_path) / "echo-args.module.yaml"
    assert path.read_text() == MODULE
    captured = capsys.readouterr()
    assert f"geschrieben: {path}" in captured.out and "Datenvorschau" in captured.out
    assert "echo-args" in fake.prompts[0].user
    assert main(["validate", str(path)]) == 0


def test_second_run_shows_diff_and_sends_current_file(
    tmp_path: Path, fake: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    fake._responses.extend([MODULE, MODULE.replace("Zeigt", "Gibt aus")])
    main(["ai", "improve-module", "echo-args", "--yes", "--apply"])
    capsys.readouterr()
    assert main(["ai", "improve-module", "echo-args", "--yes", "--apply"]) == 0
    assert "Zeigt Argumente" in fake.prompts[1].user
    assert "+summary: Gibt aus Argumente" in capsys.readouterr().out


def test_invalid_answer_saves_nothing(
    tmp_path: Path, fake: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    fake._responses.extend([MODULE + "erfunden: 1\n", MODULE.replace("echo-args", "anderes")])
    assert main(["ai", "improve-module", "echo-args", "--yes", "--apply"]) == 1
    assert "erfunden" in capsys.readouterr().err
    assert main(["ai", "improve-module", "echo-args", "--yes", "--apply"]) == 1
    assert "erwartet 'echo-args'" in capsys.readouterr().err
    assert not _modules(tmp_path).exists()


def test_no_terminal_without_yes_sends_nothing(fake: FakeProvider) -> None:
    _enable()
    assert main(["ai", "improve-module", "echo-args"]) == 2
    assert fake.prompts == []


def test_interactive_answers(
    tmp_path: Path, fake: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

    _enable()
    fake._responses.extend([MODULE, MODULE])
    monkeypatch.setattr("sys.stdin", Tty("n\n"))
    assert main(["ai", "improve-module", "echo-args"]) == 2 and fake.prompts == []
    monkeypatch.setattr("sys.stdin", Tty("j\nn\n"))
    assert main(["ai", "improve-module", "echo-args"]) == 2
    assert len(fake.prompts) == 1 and not _modules(tmp_path).exists()
    monkeypatch.setattr("sys.stdin", Tty("j\nj\n"))
    assert main(["ai", "improve-module", "echo-args"]) == 0
    assert (_modules(tmp_path) / "echo-args.module.yaml").exists()


def test_out_must_stay_in_module_folder(
    tmp_path: Path, fake: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    fake._responses.append(MODULE)
    outside = tmp_path / "x.module.yaml"
    assert (
        main(["ai", "improve-module", "echo-args", "--yes", "--apply", "--out", str(outside)]) == 1
    )
    assert "Ungültiges Ziel" in capsys.readouterr().err and not outside.exists()
    assert fake.prompts == []
    fake._responses.append(MODULE)
    assert (
        main(["ai", "improve-module", "echo-args", "--yes", "--apply", "--out", "mein.module.yaml"])
        == 0
    )
    assert (_modules(tmp_path) / "mein.module.yaml").exists()


def test_examples_and_draft_workflow(tmp_path: Path, fake: FakeProvider) -> None:
    _enable()
    fake._responses.extend([MODULE, WORKFLOW])
    assert main(["ai", "examples", "echo-args", "--yes", "--apply"]) == 0
    assert "echo-args" in fake.prompts[0].user
    assert main(["ai", "draft-workflow", "sag hallo", "--yes", "--apply"]) == 0
    assert (
        tmp_path / "xdg-config" / "whattheshell" / "workflows" / "mein-test.workflow.yaml"
    ).exists()
    fake._responses.append(WORKFLOW)
    assert main(["ai", "draft-workflow", "sag hallo", "--yes", "--apply", "--name", "x"]) == 0
    assert (tmp_path / "xdg-config" / "whattheshell" / "workflows" / "x.workflow.yaml").exists()


def _run_json(tmp_path: Path) -> str:
    step = {
        "command": "grep x f",
        "exit_code": 2,
        "stdout": f"AUSGABE-EINS {KEY}",
        "stderr": "grep: f: Datei fehlt\nzweite Zeile",
    }
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"status": "failed", "results": {"a": step}}))
    return str(path)


def test_diagnose_default_sends_no_stdout(
    tmp_path: Path, fake: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    fake._responses.append("Datei anlegen.\x1b[31m")
    assert main(["ai", "diagnose", _run_json(tmp_path), "a", "--yes"]) == 0
    sent = fake.prompts[0].user
    assert "grep x f" in sent and "Exit-Code: 2" in sent and "Dauer" in sent and "Status" in sent
    assert "AUSGABE-EINS" not in sent and "Datei fehlt" not in sent and "zweite" not in sent
    assert capsys.readouterr().out.endswith("Datei anlegen.[31m\n")
    assert not _modules(tmp_path).exists()


def test_diagnose_with_output_masks_secret_in_preview(
    tmp_path: Path,
    fake: FakeProvider,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    _enable()
    fake._responses.append("ok")
    assert main(["ai", "diagnose", _run_json(tmp_path), "a", "--include-output", "--yes"]) == 0
    captured = capsys.readouterr()
    assert "AUSGABE-EINS ***" in captured.out
    assert KEY not in captured.out + captured.err and KEY not in fake.prompts[0].user


def test_diagnose_bad_input(tmp_path: Path, fake: FakeProvider) -> None:
    _enable()
    assert main(["ai", "diagnose", _run_json(tmp_path), "nope", "--yes"]) == 1
    assert main(["ai", "diagnose", str(tmp_path / "gibt-es-nicht.json"), "a", "--yes"]) == 1
    assert fake.prompts == []


def test_provider_failure_and_missing_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()

    def boom(settings: object) -> object:
        raise ImportError("kein providers")

    monkeypatch.setattr(cli, "make_provider", boom)
    assert main(["ai", "diagnose", _run_json(tmp_path), "a", "--yes"]) == 1
    assert "kein providers" in capsys.readouterr().err


def _workflows(tmp_path: Path) -> Path:
    return tmp_path / "xdg-config" / "whattheshell" / "workflows"


def test_draft_workflow_never_overwrites_without_name(
    tmp_path: Path, fake: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    folder = _workflows(tmp_path)
    folder.mkdir(parents=True)
    existing = folder / "mein-test.workflow.yaml"
    existing.write_text("alt\n")
    fake._responses.extend([WORKFLOW, WORKFLOW, WORKFLOW.replace("hi", "neu")])
    assert main(["ai", "draft-workflow", "x", "--yes", "--apply"]) == 0
    assert existing.read_text() == "alt\n"
    assert (folder / "mein-test_2.workflow.yaml").read_text() == WORKFLOW
    assert "mein-test_2.workflow.yaml" in capsys.readouterr().out
    assert main(["ai", "draft-workflow", "x", "--yes", "--apply"]) == 0
    assert (folder / "mein-test_3.workflow.yaml").exists() and existing.read_text() == "alt\n"
    existing.write_text(WORKFLOW)
    capsys.readouterr()
    assert main(["ai", "draft-workflow", "x", "--yes", "--apply", "--name", "mein-test"]) == 0
    assert "-  - { id: a, kind: message, text: hi }" in capsys.readouterr().out
    assert "neu" in existing.read_text()


def test_yes_alone_sends_but_does_not_write(
    tmp_path: Path, fake: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    fake._responses.append(MODULE)
    assert main(["ai", "improve-module", "echo-args", "--yes"]) == 0
    captured = capsys.readouterr()
    assert MODULE in captured.out and "Mit --apply übernehmen" in captured.err
    assert not _modules(tmp_path).exists()


def test_preview_is_complete_and_can_go_to_file(
    tmp_path: Path, fake: FakeProvider, capsys: pytest.CaptureFixture[str]
) -> None:
    _enable()
    long = MODULE + "".join(f"# zeile {i}\n" for i in range(200))
    folder = _modules(tmp_path)
    folder.mkdir(parents=True)
    (folder / "echo-args.module.yaml").write_text(long)
    fake._responses.append(long)
    assert main(["ai", "improve-module", "echo-args", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "# zeile 199" in out and "Gesamtlänge" in out and "weitere Zeilen" not in out
    target = tmp_path / "preview.txt"
    fake._responses.append(long)
    assert main(["ai", "improve-module", "echo-args", "--yes", "--preview-file", str(target)]) == 0
    out = capsys.readouterr().out
    assert f"Datenvorschau geschrieben: {target}" in out and "# zeile 199" not in out
    assert "# zeile 199" in target.read_text() and target.stat().st_mode & 0o777 == 0o600


def test_bundled_module_is_baseline_and_lowered_safety_warns(
    tmp_path: Path,
    fake: FakeProvider,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundled_grep = Path(__file__).parents[2] / "src/whattheshell/bundled/modules/grep.module.yaml"
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:/usr/bin:/bin")
    _enable()
    text = bundled_grep.read_text()
    changed = text.replace("safety: safe", "safety: dangerous", 1)
    fake._responses.extend([changed.replace("safety: dangerous", "safety: caution", 1)])
    assert main(["ai", "improve-module", "grep", "--yes", "--apply"]) == 0
    assert "tool: grep" in fake.prompts[0].user and "Aktuelles Modul" in fake.prompts[0].user
    out = capsys.readouterr().out
    assert "-safety: safe" in out and "+safety: caution" in out
    # second round: now the user file is the baseline; lowering caution -> safe warns
    fake._responses.append(text)
    assert main(["ai", "improve-module", "grep", "--yes", "--apply"]) == 0
    assert "ACHTUNG: Sicherheitsklasse wird von caution auf safe gesenkt" in capsys.readouterr().out


def test_provider_error_is_masked(
    fake: FakeProvider,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    _enable()

    class Boom:
        name = "boom"

        def complete(self, prompt: object) -> str:
            raise RuntimeError(f"401 bad key {KEY}\x1b[31m")

    monkeypatch.setattr(cli, "make_provider", lambda settings: Boom())
    assert main(["ai", "diagnose", _run_json(tmp_path), "a", "--yes"]) == 1
    err = capsys.readouterr().err
    assert KEY not in err and "***" in err and "\x1b" not in err
