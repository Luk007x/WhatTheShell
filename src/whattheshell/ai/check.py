# SPDX-License-Identifier: AGPL-3.0-or-later
"""Preflight of the configured AI source (D-012); never raises, reports every gap with a hint.

Provider, network and process code is imported only after the ``ai.enabled`` gate.
"""

import shlex
import shutil
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from whattheshell.settings import AgentSettings, ApiSettings, LocalSettings, Settings

if TYPE_CHECKING:  # subproc imports subprocess: not before the gate
    from whattheshell.subproc import Result

_PROBE_TIMEOUT = 3.0
_AGENT_TIMEOUT = 10.0
_UNCHECKED = "Verbindung wird beim ersten Aufruf geprüft"
_AGENT_HINTS = {
    "claude": ("npm install -g @anthropic-ai/claude-code", "claude login"),
    "codex": ("npm install -g @openai/codex", "codex login"),
}
# Documented status commands: exit code 0 means logged in (Claude Code CLI reference,
# developers.openai.com/codex/cli/reference).
_AUTH_STATUS = {"claude": ["auth", "status"], "codex": ["login", "status"]}


@dataclass(frozen=True)
class CheckItem:
    """One checked condition; `hint` names the next step when `ok` is false."""

    name: str
    ok: bool
    detail: str
    hint: str = ""


@dataclass(frozen=True)
class CheckResult:
    """All items of a preflight; `ok` only when every item is ok."""

    ok: bool
    provider: str
    items: list[CheckItem] = field(default_factory=list)


def agents_found() -> dict[str, str | None]:
    """Absolute path of each agent CLI on PATH, else None.

    Only tells whether the program is on PATH: no version, no login check, no process started.
    """
    return {kind: shutil.which(kind) for kind in _AGENT_HINTS}


def check(settings: Settings, *, probe_network: bool = True) -> CheckResult:
    """Check the configured AI source; errors and timeouts become items, never exceptions.

    Args:
        settings: Current settings.
        probe_network: Contact the endpoint (``local``, ``api``/openai); agent CLIs run anyway.
    """
    ai = settings.ai
    if not ai.enabled:
        item = CheckItem(
            "KI aus",
            False,
            "KI-Funktionen sind ausgeschaltet.",
            "Einschalten mit `wts ai enable` oder in den Einstellungen.",
        )
        return CheckResult(False, ai.provider, [item])
    match ai.provider:
        case "local":
            items = _check_local(ai.local, probe_network)
        case "api":
            items = _check_api(ai.api, probe_network)
        case "agent":
            items = _check_agent(ai.agent)
    from .providers.http import printable  # lazy: gate first

    # details carry foreign text (server errors, model ids, program output): no terminal escapes
    items = [replace(item, detail=printable(item.detail)) for item in items]
    return CheckResult(all(item.ok for item in items), ai.provider, items)


def _model_listed(model: str, ids: list[str]) -> bool:
    """Ollama treats ``llama3`` and ``llama3:latest`` as the same model."""
    return model.removesuffix(":latest") in {i.removesuffix(":latest") for i in ids}


def _probe_models(
    base_url: str, model: str, api_key: str | None, endpoint_hint: str, model_hint: str
) -> list[CheckItem]:
    from .providers.openai_compat import OpenAICompatProvider  # lazy: gate first

    provider = OpenAICompatProvider(base_url, model, _PROBE_TIMEOUT, api_key=api_key)
    try:
        ids = provider.list_models()
    except RuntimeError as err:
        return [CheckItem("Endpunkt", False, f"{base_url}: {err}", endpoint_hint)]
    items = [CheckItem("Endpunkt", True, f"{base_url} antwortet, {len(ids)} Modelle")]
    if model and _model_listed(model, ids):
        items.append(CheckItem("Modell verfügbar", True, model))
    elif model:
        shown = ", ".join(ids[:5]) + (" …" if len(ids) > 5 else "")
        items.append(
            CheckItem(
                "Modell verfügbar", False, f"'{model}' fehlt (vorhanden: {shown})", model_hint
            )
        )
    return items


def _check_local(local: LocalSettings, probe_network: bool) -> list[CheckItem]:
    items = [
        CheckItem("Modell eingetragen", True, local.model)
        if local.model
        else CheckItem(
            "Modell eingetragen",
            False,
            "kein Modell gesetzt",
            "Modell in den Einstellungen eintragen: `wts ai config set local.model <name>`",
        )
    ]
    if not probe_network:
        return [*items, CheckItem("Endpunkt", True, f"{local.base_url} nicht geprüft", _UNCHECKED)]
    return items + _probe_models(
        local.base_url,
        local.model,
        None,
        "Ollama starten: `ollama serve`",
        f"Modell laden: `ollama pull {local.model}`",
    )


def _check_api(api: ApiSettings, probe_network: bool) -> list[CheckItem]:
    from .providers.keys import resolve_key  # lazy: gate first

    source = f"Umgebungsvariable {api.key_env}" if api.key_source == "env" else "Schlüsselbund"
    key: str | None = None
    try:
        key = resolve_key(api)
        items = [CheckItem("Schlüssel", True, f"vorhanden ({source})")]  # never the value
    except RuntimeError as err:
        items = [CheckItem("Schlüssel", False, str(err), f"Schlüssel hinterlegen ({source})")]
    items.append(
        CheckItem("Modell eingetragen", True, api.model)
        if api.model
        else CheckItem(
            "Modell eingetragen",
            False,
            "kein Modell gesetzt",
            "Modell in den Einstellungen eintragen: `wts ai config set api.model <name>`",
        )
    )
    if api.kind == "openai" and probe_network and key is not None:
        url = api.base_url or "https://api.openai.com/v1"
        return items + _probe_models(
            url, api.model, key, "Netz, Proxy und api.base_url prüfen", "Modellnamen prüfen"
        )
    detail = "kein Listen-Endpunkt" if api.kind == "anthropic" else "nicht geprüft"
    return [*items, CheckItem("Verbindung", True, detail, _UNCHECKED)]


def _check_agent(agent: AgentSettings) -> list[CheckItem]:
    from whattheshell.subproc import run_limited

    from .providers.agent_cli import CREDENTIALS, _default_command, isolated_env  # lazy: gate first

    install, login = _AGENT_HINTS[agent.kind]
    program = agent.kind
    path = shutil.which(program)
    if path is None:
        return [
            CheckItem("Programm", False, f"`{program}` nicht im PATH", f"Installieren: `{install}`")
        ]
    line = _default_command(agent.kind, agent.model, agent.reasoning)
    items = [
        CheckItem("Programm", True, path),
        CheckItem("Aufrufzeile", True, shlex.join(line)),  # no secrets: the prompt goes via stdin
    ]
    try:
        with isolated_env(agent.kind) as (env, work):
            version = run_limited(
                [path, "--version"], timeout=_AGENT_TIMEOUT, max_bytes=65536, env=env,
                cwd=str(work),
            )  # fmt: skip
            # Same throwaway HOME as a real call: checks the copied login, not the user's HOME.
            auth = run_limited(
                [path, *_AUTH_STATUS[agent.kind]], timeout=_AGENT_TIMEOUT, max_bytes=65536,
                env=env, cwd=str(work),
            )  # fmt: skip
    except OSError as err:
        detail = f"Anmeldedatei nicht kopierbar: {err}"
        hint = f"Rechte von ~/{CREDENTIALS[agent.kind]} prüfen"
        return [*items, CheckItem("Anmeldung", False, detail, hint)]
    if version is None or version.timed_out or version.exit_code != 0:
        items.append(
            CheckItem("Version", False, _failure(version), f"Neu installieren: `{install}`")
        )
    else:
        first = version.stdout.decode(errors="replace").strip().splitlines()[:1]
        items.append(CheckItem("Version", True, first[0][:80] if first else "?"))
    if auth is None or auth.timed_out or auth.exit_code != 0:
        detail = f"nicht angemeldet ({_failure(auth)}; geprüft mit ~/{CREDENTIALS[agent.kind]})"
        items.append(CheckItem("Anmeldung", False, detail, f"Anmelden: `{login}`"))
    else:
        items.append(CheckItem("Anmeldung", True, "angemeldet"))  # output may hold the e-mail
    return items


def _failure(result: "Result | None") -> str:
    """Short reason of a failed `run_limited` call (None = not startable)."""
    if result is None:
        return "Programm nicht startbar"
    if result.timed_out:
        return f"Zeitlimit {_AGENT_TIMEOUT:g} s überschritten"
    return f"Exit-Code {result.exit_code}"
