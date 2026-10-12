# Entscheidungen

Jede Abweichung vom Projektauftrag und jede offene Wahl, die der Auftrag an Claude Code delegiert, steht hier mit Begründung.

## D-001 Namensprüfung „WhatTheShell" (Projektauftrag 18.1), 2026-10-12

| Prüfung | Ergebnis |
|---|---|
| PyPI `whattheshell` | frei (JSON-Seite liefert 404) |
| PyPI `what-the-shell` | frei (404) |
| GitHub | ~13 kleine Repos mit dem Namen, keines über 10 Sterne, keine Produkte; Verwechslungsgefahr gering |
| `command -v wts` (Fedora 44) | kein Treffer; `dnf provides '*/bin/wts'` leer |
| Debian-Paketinhalte, Datei `wts` (stable) | kein Paket liefert eine Datei `wts` |
| Domain, DPMA/EUIPO | nicht geprüft, vor Veröffentlichung nachholen |

Ergebnis: Name und Alias `wts` werden verwendet. Platzhalter-Paket auf PyPI erst nach Rücksprache (18.1 Punkt 5).

## D-002 Lizenz, 2026-10-12

Code: **AGPL-3.0-or-later** (Projektauftrag 18.2, vom Auftraggeber bestätigt). Mitgelieferte Module und Workflows unter `modules/` und `workflows/`: **CC0-1.0**, damit sie ohne Copyleft-Hürde geteilt werden können. Nutzerdateien gehören den Nutzern. Keine Rechtsberatung, vor Veröffentlichung prüfen lassen.

## D-003 Arbeitsweise, 2026-10-12

Hauptsession ist Manager und delegiert an Sonnet-/Haiku-Agenten (siehe `CLAUDE.md`). Eine Contract-first-Vorlage je Modul (`CONTRACT.md`) wird auf Wunsch des Auftraggebers nicht verwendet; Modulzwecke stehen stattdessen knapp in `docs/ARCHITECTURE.md`.

## D-004 Formate (Projektauftrag 8.3), 2026-10-12

- Workflow ist ein **strukturierter Baum** (Schrittfolgen, Kontrollstrukturen mit Teilfolgen), kein freier Graph. Kanten werden aus dem Baum abgeleitet, nicht gespeichert. Grund: nur so sind Knoten-Graph und Block-Ansicht per Konstruktion verlustfrei (F-32, F-35). Details `docs/FORMATS.md`.
- Listen-Typen über `multiple: true` statt `path[]`: bleibt ein Enum im Schema, einfacher für KI und Validierung.
- `OptionSpec`/`InputSpec` werden von Katalog und Modul geteilt. Ein Modell statt zwei, Merge über `model_fields_set`.
- CLI mit `argparse` (Stdlib) statt Typer/Click: keine Abhängigkeit, Subparser reichen.
- YAML mit `ruamel.yaml`: Kommentare und Reihenfolge bleiben im In-App-Editor erhalten, Zeilennummern für Fehlermeldungen.

## D-005 Ergänzungen nach Review Phase 0, 2026-10-12

- `CommandStep.ok_exit_codes` (Standard `[0]`) statt `on_error: continue` für Tools wie `grep`/`diff`, bei denen Exit 1 kein Fehler ist. `continue` würde echte Fehler (Exit 2) mitschlucken.
- Secrets nur über `type: secret`, kein zweites Flag `secret: true`. Ein `default` ist bei Secrets verboten (Klartext in Datei).
- Kein `$id` in den exportierten Schemas, bis es einen echten Hosting-Pfad gibt. Repo-URL nicht im Code.
- `env` in Workflow-Schritten wird beim Ausführen gefiltert (`LD_PRELOAD`, `PATH` u. a.), Entscheidung in Phase 3 in `docs/SECURITY.md`.
- Konsistenzprüfungen an `OptionSpec` (enum ohne choices, min > max, default passt nicht zum Typ) kommen in Phase 2 mit dem Modul-Lader.
