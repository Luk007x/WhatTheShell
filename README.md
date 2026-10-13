# WhatTheShell

Ein Linux-Programm mit grafischer Oberfläche, in dem man Kommandozeilen-Tools wie Bausteine
zu Workflows zusammenklickt, ausführt und die Ausgaben auswertet.

**Status:** Phasen 0 bis 7 umgesetzt (CLI, Web-GUI mit Knoten-Graph und Block-Ansicht, Modul-Editor, optionale KI-Funktionen, eingebettetes Terminal für interaktive Programme). Phasenplan in `PROJEKTAUFTRAG.md`.

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
wts workflows                    # Bibliothek: mitgeliefert, ~/.config/whattheshell/workflows, ./.whattheshell/workflows
wts run workflow.yaml|ID         # Ausführen mit Bestätigung für caution/dangerous
wts gui                          # Web-Oberfläche auf 127.0.0.1 mit Sitzungstoken
wts ai status                    # KI-Funktionen (standardmäßig aus): enable, check, config set, improve-module, examples, draft-workflow, diagnose
wts terminal transcripts         # Transkripte von Terminal-Schritten auflisten, --delete NAME löscht eines
```

Voraussetzungen: Linux, Python ≥ 3.11, `bubblewrap` (`bwrap`) für Vorschau, Beispiele und Terminal-Schritte (interaktive Programme wie `vim`, `less`, `top` laufen nur in der GUI, immer in der Sandbox; Regeln in `docs/SECURITY.md`, Abschnitt 7).

## Installation

```
sudo apt install bubblewrap pipx          # bzw. Paketmanager der Distribution
pipx install whattheshell                 # sobald auf PyPI veröffentlicht
pipx install ./whattheshell-0.0.1-py3-none-any.whl   # oder aus dem Wheel (CI-Artefakt / Release)
wts gui
```

Node wird nur zum Bauen benötigt, nicht zur Laufzeit: Das Wheel enthält das fertige Frontend.

## Starten und Beenden

```
wts gui start               # im Hintergrund starten, Browser öffnen (läuft schon eine Instanz: nur Browser)
wts gui status              # Port, PID, Laufzeit; Exit 3 = nicht gestartet
wts gui stop                # beenden (SIGTERM, nach 5 s SIGKILL)
wts gui                     # im Vordergrund, Strg+C beendet; ein zweites `wts gui` startet keinen zweiten Server
wts gui --install-desktop   # Menüeintrag "WhatTheShell" (~/.local/share/applications), ruft `wts gui start`
```

Zustand: `$XDG_RUNTIME_DIR/whattheshell/gui.json`, Log des Hintergrundservers: `~/.cache/whattheshell/gui.log`.

## Release

`git tag vX.Y.Z && git push --tags` baut das Wheel und hängt es an das GitHub-Release.
Veröffentlichen auf PyPI lokal: `scripts/build_wheel.sh && uv publish dist/*`.

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
