# SPDX-License-Identifier: AGPL-3.0-or-later
"""AI tasks as pure functions: build prompts, evaluate answers. No I/O towards a model."""

import os
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from whattheshell.ai.protocol import Prompt
from whattheshell.engine import mask_text

__all__ = [
    "diagnose",
    "draft_workflow",
    "extract_yaml",
    "generate_examples",
    "improve_module",
    "known_keys",
    "sanitize",
]

OUTPUT_LIMIT = 4000

_ONLY_YAML = (
    "Ausgabe: genau eine YAML-Datei, beginnend mit `schema_version: 1`, keine Erklärung, "
    "keine Markdown-Zäune."
)
# Short rules instead of the full MODULE_AUTHORING.md (D-012): role, inputs, exact output.
_MODULE_SYSTEM = f"""Rolle: Du schreibst ein WhatTheShell-Modul für den Befehl TOOL.
Eingaben:
- inspect-JSON: Ausgabe von `wts inspect TOOL --json` (Optionen, Eingaben, ids)
- aktuelles Modul, falls vorhanden
{_ONLY_YAML} Dateiname TOOL.module.yaml.
Regeln:
- Kopf: schema_version: 1, tool: TOOL, override_mode: merge; Optionen werden nach id \
zusammengeführt, angegebene Felder überschreiben.
- Alle Texte (display_name, summary, label, help, group) auf Deutsch, kurz, für Einsteiger; \
englisch in i18n: {{en: {{display_name, summary, options: {{id: {{label, help}}}}, \
inputs: {{id: {{label, help}}}}}}}}.
- ids nur aus der inspect-JSON; keine erfundenen ids, Optionen oder Felder.
- inputs ersetzen die Katalog-Eingaben vollständig (Reihenfolge = Argumentreihenfolge); \
before_options: true, wenn ein Argument vor den Optionen stehen muss (z. B. start bei find).
- Optionen in Gruppen (group); 5-8 wichtige mit importance: common, seltene mit rare.
- safety: safe (liest nur), caution (schreibt/ändert umkehrbar), dangerous (löscht, \
überschreibt, wirkt auf System/Rechte); löschende oder überschreibende Optionen anheben, im \
Zweifel höher.
- 2-3 Beispiele: title, fixtures (path relativ ohne .., content), args (Schlüssel = ids), \
expect (nur exit_code, stdout_contains, stderr_contains, stdout_regex); klein, \
deterministisch, ohne Netz, nichts außerhalb des Arbeitsordners.
- Keine type: secret mit default; output.exit_codes nur, wenn die Hilfe sie nennt."""

_WORKFLOW_SYSTEM = f"""Rolle: Du entwirfst einen WhatTheShell-Workflow aus einer Beschreibung.
Eingaben:
- Beschreibung
- verfügbare Tools mit ihren Option-/Input-ids
{_ONLY_YAML}
Felder:
- Kopf: schema_version: 1, name, description, variables (Schlüssel = id: {{type, default, \
label}}), steps; type: string|int|float|bool|path|enum|secret, enum mit choices, Zahlen \
optional min/max, secret ohne default.
- Jeder Schritt: id (eindeutig, ^[a-z][a-z0-9_]*$, nicht var/item), kind.
- command: tool, command (Subbefehl-Pfad, z. B. ["commit"] bei git), args (Schlüssel = ids \
des Moduls), extra_args, stdin ({{pipe: id}} | {{text}} | {{file}}), ok_exit_codes, on_error \
({{action: abort|continue}}, retry nur mit retries: n, fallback nur mit steps: [...]).
- if: condition ({{source, ein Operator wie eq, contains, is_empty, number_gt}}), then, else.
- foreach: source, as, body. set: variable, value. wait: seconds. message: text. abort: text.
- Templates nur {{{{ var.name }}}}, {{{{ schritt_id.stdout }}}} (auch stderr, exit_code, \
lines), {{{{ item }}}}; nur frühere Schritte referenzieren.
Regeln: keine erfundenen Felder oder ids, keine Shell-Konstrukte, nur argv."""

_DIAGNOSE_SYSTEM = (
    "Rolle: Du hilfst Einsteigern, einen fehlgeschlagenen Befehl zu verstehen. "
    "Nenne wahrscheinliche Ursachen und konkrete Korrekturvorschläge auf Deutsch, kurz. "
    "Du lieferst nur Text; nichts wird ausgeführt."
)


def _module_task(tool: str, task: str, current_raw: str | None, inspect_json: str) -> Prompt:
    """Rules and task in the system prompt; the user prompt holds only the data."""
    parts = [f"inspect-JSON:\n{inspect_json}"]
    if current_raw is not None:
        parts.append(f"Aktuelles Modul:\n{current_raw}")
    system = _MODULE_SYSTEM.replace("TOOL", tool)
    return Prompt(f"{system}\nAuftrag: {task}", "\n\n".join(parts))


def improve_module(tool: str, *, current_raw: str | None, inspect_json: str) -> Prompt:
    """Prompt to write or improve the module of `tool` (descriptions, groups, defaults)."""
    task = (
        "Verbessere das aktuelle Modul (Beschreibungen, Gruppierung, Standardwerte)."
        if current_raw is not None
        else "Schreibe ein neues Modul."
    )
    return _module_task(tool, task, current_raw, inspect_json)


def generate_examples(tool: str, current_raw: str, inspect_json: str) -> Prompt:
    """Prompt to add examples and fixtures to the existing module, everything else unchanged."""
    task = (
        "Ergänze 2-3 Beispiele mit fixtures, args und expect. Ändere nichts anderes. "
        "Gib das vollständige Modul zurück."
    )
    return _module_task(tool, task, current_raw, inspect_json)


def draft_workflow(description: str, tools_hint: str) -> Prompt:
    """Prompt to draft a workflow file from a free-text description."""
    user = f"Beschreibung:\n{description}\n\nVerfügbare Tools und ihre ids:\n{tools_hint}"
    return Prompt(_WORKFLOW_SYSTEM, user)


def _clip(text: str) -> str:
    return text if len(text) <= OUTPUT_LIMIT else text[:OUTPUT_LIMIT] + "\n[gekürzt]"


def _duration(step: Mapping[str, Any]) -> str:
    try:
        seconds = (
            datetime.fromisoformat(str(step["finished"]))
            - datetime.fromisoformat(str(step["started"]))
        ).total_seconds()
    except (KeyError, ValueError):
        return "unbekannt"
    return f"{seconds:.2f}s"


def diagnose(step: Mapping[str, Any], include_output: bool) -> Prompt:
    """Prompt to explain a failed step.

    Without `include_output` only command, exit code, duration and status are sent; no
    output line, not even from stderr.
    """
    lines = [
        f"Befehl: {step.get('command')}",
        f"Exit-Code: {step.get('exit_code')}",
        f"Dauer: {_duration(step)}",
        f"Status: {'ok' if step.get('ok') else 'fehlgeschlagen'}",
    ]
    if include_output:
        lines += [
            f"stdout:\n{_clip(str(step.get('stdout') or ''))}",
            f"stderr:\n{_clip(str(step.get('stderr') or ''))}",
        ]
    return Prompt(_DIAGNOSE_SYSTEM, "\n".join(lines))


_KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CODEX_API_KEY")


def known_keys(key_env: str) -> list[str]:
    """Values of the configured and the usual key variables that are set, longest first."""
    values = {os.environ.get(name, "") for name in (key_env, *_KEY_VARS)} - {""}
    return sorted(values, key=len, reverse=True)


def sanitize(text: str, secrets: Sequence[str]) -> str:
    """Mask secrets and drop control characters (terminal escapes) from untrusted text."""
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", mask_text(text, secrets))


_START = re.compile(r"^(schema_version|tool|name):")
_FENCED = re.compile(r"```[\w-]*\n(.*?)```", re.DOTALL)


def extract_yaml(text: str) -> str:
    """Strip Markdown fences and text before the first ``schema_version:``/``tool:``/``name:``."""
    fenced = _FENCED.search(text)
    if fenced:
        text = fenced.group(1)
    lines = [line for line in text.splitlines() if not line.startswith("```")]
    start = next((i for i, line in enumerate(lines) if _START.match(line)), 0)
    return "\n".join(lines[start:]).strip() + "\n"
