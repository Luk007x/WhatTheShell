# SPDX-License-Identifier: AGPL-3.0-or-later
"""Preflight of the configured AI source (D-012); never raises, reports every gap with a hint.

Provider, network and process code is imported only after the ``ai.enabled`` gate.
"""

import shlex
import shutil
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from whattheshell.i18n import _
from whattheshell.settings import AgentSettings, ApiSettings, LocalSettings, Settings

if TYPE_CHECKING:  # subproc imports subprocess: not before the gate
    from whattheshell.subproc import Result

_PROBE_TIMEOUT = 3.0
_AGENT_TIMEOUT = 10.0
_AGENT_HINTS = {
    "claude": ("npm install -g @anthropic-ai/claude-code", "claude login"),
    "codex": ("npm install -g @openai/codex", "codex login"),
}
# Documented status commands: exit code 0 means logged in (Claude Code CLI reference,
# developers.openai.com/codex/cli/reference).
_AUTH_STATUS = {"claude": ["auth", "status"], "codex": ["login", "status"]}


def _unchecked() -> str:
    return _("Verbindung wird beim ersten Aufruf geprüft")


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
            _("KI aus"),
            False,
            _("KI-Funktionen sind ausgeschaltet."),
            _("Einschalten mit `wts ai enable` oder in den Einstellungen."),
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
        return [CheckItem(_("Endpunkt"), False, f"{base_url}: {err}", endpoint_hint)]
    items = [
        CheckItem(
            _("Endpunkt"), True, _("{url} antwortet, {count} Modelle", url=base_url, count=len(ids))
        )
    ]
    if model and _model_listed(model, ids):
        items.append(CheckItem(_("Modell verfügbar"), True, model))
    elif model:
        shown = ", ".join(ids[:5]) + (" …" if len(ids) > 5 else "")
        items.append(
            CheckItem(
                _("Modell verfügbar"),
                False,
                _("'{model}' fehlt (vorhanden: {shown})", model=model, shown=shown),
                model_hint,
            )
        )
    return items


def _check_local(local: LocalSettings, probe_network: bool) -> list[CheckItem]:
    items = [
        CheckItem(_("Modell eingetragen"), True, local.model)
        if local.model
        else CheckItem(
            _("Modell eingetragen"),
            False,
            _("kein Modell gesetzt"),
            _("Modell in den Einstellungen eintragen: `wts ai config set local.model <name>`"),
        )
    ]
    if not probe_network:
        return [
            *items,
            CheckItem(
                _("Endpunkt"), True, _("{url} nicht geprüft", url=local.base_url), _unchecked()
            ),
        ]
    return items + _probe_models(
        local.base_url,
        local.model,
        None,
        _("Ollama starten: `ollama serve`"),
        _("Modell laden: `ollama pull {model}`", model=local.model),
    )


def _check_api(api: ApiSettings, probe_network: bool) -> list[CheckItem]:
    from .providers.keys import resolve_key  # lazy: gate first

    source = (
        _("Umgebungsvariable {name}", name=api.key_env)
        if api.key_source == "env"
        else _("Schlüsselbund")
    )
    key: str | None = None
    try:
        key = resolve_key(api)
        items = [
            CheckItem(_("Schlüssel"), True, _("vorhanden ({source})", source=source))
        ]  # never the value
    except RuntimeError as err:
        items = [
            CheckItem(
                _("Schlüssel"),
                False,
                str(err),
                _("Schlüssel hinterlegen ({source})", source=source),
            )
        ]
    items.append(
        CheckItem(_("Modell eingetragen"), True, api.model)
        if api.model
        else CheckItem(
            _("Modell eingetragen"),
            False,
            _("kein Modell gesetzt"),
            _("Modell in den Einstellungen eintragen: `wts ai config set api.model <name>`"),
        )
    )
    if api.kind == "openai" and probe_network and key is not None:
        url = api.base_url or "https://api.openai.com/v1"
        return items + _probe_models(
            url,
            api.model,
            key,
            _("Netz, Proxy und api.base_url prüfen"),
            _("Modellnamen prüfen"),
        )
    detail = _("kein Listen-Endpunkt") if api.kind == "anthropic" else _("nicht geprüft")
    return [*items, CheckItem(_("Verbindung"), True, detail, _unchecked())]


def _check_agent(agent: AgentSettings) -> list[CheckItem]:
    from whattheshell.subproc import run_limited

    from .providers.agent_cli import CREDENTIALS, _default_command, isolated_env  # lazy: gate first

    install, login = _AGENT_HINTS[agent.kind]
    program = agent.kind
    path = shutil.which(program)
    if path is None:
        return [
            CheckItem(
                _("Programm"),
                False,
                _("`{program}` nicht im PATH", program=program),
                _("Installieren: `{install}`", install=install),
            )
        ]
    line = _default_command(agent.kind, agent.model, agent.reasoning)
    items = [
        CheckItem(_("Programm"), True, path),
        CheckItem(
            _("Aufrufzeile"), True, shlex.join(line)
        ),  # no secrets: the prompt goes via stdin
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
        detail = _("Anmeldedatei nicht kopierbar: {err}", err=err)
        hint = _("Rechte von ~/{file} prüfen", file=CREDENTIALS[agent.kind])
        return [*items, CheckItem(_("Anmeldung"), False, detail, hint)]
    if version is None or version.timed_out or version.exit_code != 0:
        items.append(
            CheckItem(
                _("Version"),
                False,
                _failure(version),
                _("Neu installieren: `{install}`", install=install),
            )
        )
    else:
        first = version.stdout.decode(errors="replace").strip().splitlines()[:1]
        items.append(CheckItem(_("Version"), True, first[0][:80] if first else "?"))
    if auth is None or auth.timed_out or auth.exit_code != 0:
        detail = _(
            "nicht angemeldet ({failure}; geprüft mit ~/{file})",
            failure=_failure(auth),
            file=CREDENTIALS[agent.kind],
        )
        items.append(
            CheckItem(_("Anmeldung"), False, detail, _("Anmelden: `{login}`", login=login))
        )
    else:
        items.append(CheckItem(_("Anmeldung"), True, _("angemeldet")))  # output may hold the e-mail
    return items


def _failure(result: "Result | None") -> str:
    """Short reason of a failed `run_limited` call (None = not startable)."""
    if result is None:
        return _("Programm nicht startbar")
    if result.timed_out:
        return _("Zeitlimit {timeout:g} s überschritten", timeout=_AGENT_TIMEOUT)
    return _("Exit-Code {code}", code=result.exit_code)
