# Architektur

Stand: Phase 1. Pakete, die noch nicht existieren, sind als „geplant" markiert und tragen den Phasenbezug aus dem Projektauftrag (Abschnitt 16).

## Datenfluss

```
Tool auf PATH → helpparse → Roh-Katalog (CommandSpec) → + Modul-Overrides (merge) → fertiger Baustein
      → GUI / CLI → Workflow-Datei (strukturierter Baum) → engine → Ergebnis → Evaluator → nächster Schritt
```

Der Kern (`src/whattheshell/`) hat keine GUI-Abhängigkeit. Die Web-UI unter `gui/` redet nur über `api/` mit dem Kern.
Die Datenmodelle sind die einzige Quelle der Wahrheit; `schemas/` wird daraus generiert (`wts schema export`).

## Pakete

| Paket | Zweck | Öffentliche Schnittstelle | Nicht zuständig für | Phase |
|---|---|---|---|---|
| `models` | Pydantic-Modelle für Katalog, Modul und Workflow, Validierung, Migration, Schema-Export | `Module`, `Workflow`, `iter_steps`, `migrate`, `export_schemas`, `format_validation_error`, `CommandSpec`, `ToolInfo` | Laden von Dateien, Mergen, Ausführen | 0 |
| `cli` | `wts`-Einstieg, argparse-Subcommands (`schema export`, `tools`, `inspect`) | `main(argv) -> int` | Fachlogik; ruft nur Paketfunktionen | 0 |
| `subproc` | Begrenzter Prozessstart: argv, eigene Prozessgruppe, Timeout, Byte-Limit, bereinigte Umgebung | `run_limited`, `sanitized_env` | Entscheidung, was gestartet wird | 1 |
| `catalog` | PATH durchsuchen, Hilfe lazy holen (`--help`, `-h`, `man`), Cache nach `path + mtime + size` (innen `help_hash`, `version`), Subbefehle mit Tiefenlimit, interaktive Tools markieren | `scan_path`, `Catalog.tools/get`, `fetch_help`, `ToolNotFound`, `INTERACTIVE`, `NEVER_PROBE` | Parsen der Hilfe | 1 |
| `helpparse` | Reiner Text → `CommandSpec` mit Konfidenz je Option, Fallback „Freie Argumente" (`raw_help`); Golden-Korpus in `tests/corpus/` | `parse_help`, `clean_text` | Prozessstart, Cache | 1 |
| `paths` | XDG-Verzeichnisse | `cache_dir` | – | 1 |
| `modules` | Modul-Dateien laden, validieren, mit Katalog mergen, Hot-Reload, `validate`/`scaffold` | geplant | Workflow-Dateien | 2 |
| `safety` | Gefahrenklasse je Befehl/Option, Bestätigungslogik | geplant | Ausführung | 3 |
| `sandbox` | `bwrap`-Vorschau, Selbsttest, Limits | geplant | Entscheidung, was ausgeführt wird | 3 |
| `engine` | Workflow-Ausführung: argv-Aufbau, Pipes, Variablen, Templates, Evaluatoren, Fehlerbehandlung, Dry-Run | geplant | Sandbox, GUI | 3 |
| `api` | FastAPI + WebSocket auf 127.0.0.1 mit Token, liefert das vorgebaute Frontend aus | geplant | Fachlogik | 4 |
| `ai` | Optionale Provider (lokal, API, Agenten-CLI), standardmäßig nicht importiert | geplant | Ausführen von Ergebnissen | 6 |
| `terminal` | Eingebettetes Terminal (PTY) | geplant | – | 7 |

## Modell-Invarianten (Kurzfassung, Details in `FORMATS.md`)

- Jedes Dokument trägt `schema_version`; `migrate` hebt ältere Versionen an, bevor validiert wird.
- Unbekannte Felder sind Fehler (`extra="forbid"`), damit Tippfehler von Menschen und KI auffallen.
- Workflow = strukturierter Baum. Kanten für den Knoten-Graph werden abgeleitet, nie gespeichert. `layout` ist optional und trägt nur Positionen.
- Referenzen (`stdin.pipe`, `condition.source`, `{{ … }}`) zeigen nur auf sichtbare frühere Schritte, deklarierte Variablen oder umschließende `foreach`-Namen.
- Pfade in Modulen sind relativ und ohne `..`; `tool`-Namen sind keine Pfade.

## Tests

`tests/unit/` je Paket. `tests/corpus/` hält 29 echte Hilfetexte mit per Hand erstellten `expected.json`; `test_corpus.py` misst Options-Recall (Schwelle 90 % gesamt, 75 % je Tool), Typtreue (90 %) und Subbefehl-Recall (90 %). Neue Parserfehler werden zuerst dort als Fall angelegt. Drift-Test stellt sicher, dass `schemas/` zum Code passt.
