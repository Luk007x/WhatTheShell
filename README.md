# WhatTheShell

Ein Linux-Programm mit grafischer Oberfläche, in dem man Kommandozeilen-Tools wie Bausteine
zu Workflows zusammenklickt, ausführt und die Ausgaben auswertet.

**Status:** Phase 3 abgeschlossen (Kern per CLI nutzbar, noch keine GUI). Phasenplan in `PROJEKTAUFTRAG.md`.

## Was geht schon (CLI)

```
wts tools --search grep          # installierte Tools finden
wts inspect grep                 # Optionen, Typen, Hilfetexte, Konfidenz (Module eingerechnet)
wts scaffold wc --user           # Modulgerüst nach ~/.config/whattheshell/modules/
wts validate datei.module.yaml   # Modul oder Workflow prüfen
wts modules [--watch]            # geladene Module, Hot-Reload
wts sandbox                      # bwrap-Selbsttest mit Installationshinweis
wts example grep                 # Modul-Beispiele in der Sandbox ausführen
wts run workflow.yaml --dry-run  # Plan mit Gefahrenklassen, nichts wird ausgeführt
wts run workflow.yaml            # Ausführen mit Bestätigung für caution/dangerous
```

Voraussetzungen: Linux, Python ≥ 3.11, `bubblewrap` (`bwrap`) für Vorschau und Beispiele.

## Entwicklung

```
uv sync --group dev
uv run wts --version
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

## Lizenz

Code: AGPL-3.0-or-later (siehe `LICENSE`). Mitgelieferte Module und Workflows
(`src/whattheshell/bundled/`): CC0-1.0. Sicherheitskonzept: `docs/SECURITY.md`.
