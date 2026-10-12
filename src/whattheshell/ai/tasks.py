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
    "Antworte NUR mit dem YAML-Inhalt, ohne Markdown-Zäune, ohne Text davor oder danach, "
    "ohne Erklärungen."
)
_MODULE_SYSTEM = f"""Rolle: Du schreibst ein WhatTheShell-Modul für den Befehl TOOL.

Qualitätsregeln:
- schema_version: 1, tool: TOOL, override_mode: merge.
- Alle Texte (display_name, summary, label, help, group) auf Deutsch, kurz und für Einsteiger \
verständlich; i18n.en mit englischen Texten.
- ids ausschließlich aus der inspect-Ausgabe; keine erfundenen ids oder Felder.
- Optionen in sinnvolle Gruppen (group) ordnen; 5-8 Optionen mit importance: common, seltene mit \
rare.
- 2-3 Beispiele mit fixtures, args (Schlüssel = ids) und expect; klein, deterministisch, relative \
Pfade, kein Netzwerk, nichts außerhalb des Arbeitsordners.
- output.exit_codes befüllen, wenn die Man-Page Exit-Codes nennt.
- safety: Befehl und Optionen nach Abschnitt 5 der Anleitung einstufen; löschende oder \
überschreibende Optionen anheben.
- Keine type: secret mit default.
Ausgabe: genau eine YAML-Datei TOOL.module.yaml. {_ONLY_YAML}"""

_WORKFLOW_SYSTEM = f"""Rolle: Du entwirfst einen WhatTheShell-Workflow aus einer Beschreibung.

Format (Kurzfassung): schema_version: 1, name, description, variables (Schlüssel = id), steps.
Jeder Schritt hat eine eindeutige id (^[a-z][a-z0-9_]*$, nicht var/item). kind: command (tool, \
args mit Schlüsseln = Option-/Input-ids des Moduls, extra_args, stdin: {{pipe: id}} | {{text}} | \
{{file}}, ok_exit_codes, on_error), if (condition, then, else), foreach (source, as, body), \
set, wait, message, abort.
Variablen und Schritt-Ausgaben nur als {{{{ var.name }}}}, {{{{ schritt_id.stdout }}}} \
(auch stderr, exit_code, lines), {{{{ item }}}}; Schritte dürfen nur frühere Schritte \
referenzieren. Keine erfundenen Felder, keine Shell-Konstrukte, nur argv.
{_ONLY_YAML}"""

_DIAGNOSE_SYSTEM = (
    "Rolle: Du hilfst Einsteigern, einen fehlgeschlagenen Befehl zu verstehen. "
    "Nenne wahrscheinliche Ursachen und konkrete Korrekturvorschläge auf Deutsch, kurz. "
    "Du lieferst nur Text; nichts wird ausgeführt."
)


def _module_prompt(tool: str, task: str, current_raw: str | None, inspect_json: str) -> str:
    parts = [
        f"Befehl TOOL = {tool}",
        task,
        f"Ausgabe von `wts inspect {tool} --json`:\n{inspect_json}",
    ]
    if current_raw is not None:
        parts.append(f"Aktuelles Modul:\n{current_raw}")
    return "\n\n".join(parts)


def improve_module(
    tool: str, *, current_raw: str | None, inspect_json: str, authoring_doc: str
) -> Prompt:
    """Prompt to write or improve the module of `tool` (descriptions, groups, defaults)."""
    task = (
        "Verbessere das aktuelle Modul (Beschreibungen, Gruppierung, Standardwerte)."
        if current_raw is not None
        else "Schreibe ein neues Modul."
    )
    user = _module_prompt(tool, task, current_raw, inspect_json)
    return Prompt(
        _MODULE_SYSTEM.replace("TOOL", tool),
        f"{user}\n\nAnleitung (docs/MODULE_AUTHORING.md):\n{authoring_doc}",
    )


def generate_examples(tool: str, current_raw: str, inspect_json: str) -> Prompt:
    """Prompt to add examples and fixtures to the existing module, everything else unchanged."""
    task = (
        "Ergänze 2-3 Beispiele mit fixtures, args und expect. Ändere nichts anderes. "
        "Gib das vollständige Modul zurück."
    )
    return Prompt(
        _MODULE_SYSTEM.replace("TOOL", tool),
        _module_prompt(tool, task, current_raw, inspect_json),
    )


def draft_workflow(description: str, tools_hint: str, formats_doc_excerpt: str) -> Prompt:
    """Prompt to draft a workflow file from a free-text description."""
    user = (
        f"Beschreibung:\n{description}\n\n"
        f"Verfügbare Tools und ihre ids:\n{tools_hint}\n\n"
        f"Formatbeschreibung:\n{formats_doc_excerpt}"
    )
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
