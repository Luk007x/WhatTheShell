# Architektur

Stand: Phase 3. Pakete, die noch nicht existieren, sind als „geplant" markiert und tragen den Phasenbezug aus dem Projektauftrag (Abschnitt 16).

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
| `cli` | `wts`-Einstieg, argparse-Subcommands (`schema export`, `tools`, `inspect`, `validate`, `scaffold`, `modules`, `run`, `example`, `sandbox`) | `main(argv) -> int` | Fachlogik; ruft nur Paketfunktionen | 0 |
| `subproc` | Begrenzter Prozessstart: argv, eigene Prozessgruppe, Timeout, Byte-Limit, bereinigte Umgebung | `run_limited`, `sanitized_env` | Entscheidung, was gestartet wird | 1 |
| `catalog` | PATH durchsuchen, Hilfe lazy holen (`--help`, `-h`, `man`), Cache nach `path + mtime + size` (innen `help_hash`, `version`), Subbefehle mit Tiefenlimit, interaktive Tools markieren, Modul-Overrides nach dem Cache anwenden (`Catalog(registry=…)`) | `scan_path`, `Catalog.tools/get`, `fetch_help`, `ToolNotFound`, `INTERACTIVE`, `NEVER_PROBE` | Parsen der Hilfe | 1 |
| `helpparse` | Reiner Text → `CommandSpec` mit Konfidenz je Option, Fallback „Freie Argumente" (`raw_help`); Golden-Korpus in `tests/corpus/` | `parse_help`, `clean_text` | Prozessstart, Cache | 1 |
| `paths` | XDG-Verzeichnisse und Modul-Suchpfade | `cache_dir`, `config_dir`, `module_dirs` | – | 1 |
| `modules` | Modul-/Workflow-Dateien laden mit Zeilennummern, Registry über Suchpfade mit isolierten Fehlern, Merge nach FORMATS §6, Hot-Reload (`watchfiles`), Modul-Gerüst | `load_document`, `load_module_file`, `load_workflow_file`, `DocumentError`, `ModuleRegistry`, `LoadedModule`, `apply_modules`, `merge_command`, `watch_modules`, `scaffold_module` | Ausführen, Katalog-Cache | 2 |
| `bundled` | Mitgelieferte Module und Workflows als Paketdaten | `MODULES_DIR`, `WORKFLOWS_DIR` | – | 2 |
| `safety` | Gefahrenklasse je Befehl und Option: Basis aus Katalog/Modul, Tool-Listen, Flag-Muster, `extra_args` | `classify_command`, `Verdict`, `summarize`, `needs_confirmation` | Ausführung, Prozesse | 3 |
| `sandbox` | `bwrap`-Aufruf (ro-root, tmpfs für /home /tmp /run, `--unshare-all`, `--clearenv`, Workdir unter `/tmp/work`), Selbsttest mit Distro-Hinweis, Zeit-/Speicher-/Ausgabelimit, Beispiel-Läufer | `self_test`, `SandboxStatus`, `run_sandboxed`, `build_bwrap_argv`, `run_example`, `iter_examples` | Entscheidung, was ausgeführt wird; Fallback ohne bwrap (gibt es nicht) | 3 |
| `engine` | argv-Aufbau aus Spec + args (nie Shell), Templates (`{{ }}`, eingeschränkt), Evaluatoren, Runner (Schritte, Pipe als aufgezeichnete Ausgabe, if/foreach/set/wait/message/abort, on_error, Bestätigung, Maskierung, env-Sperrliste, Events, Controller mit Abbruch/Pause/Einzelschritt), Plan (Dry-Run) | `build_argv`, `render`, `evaluate`, `Runner.prepare/run`, `plan`, `plan_text`, `Controller`, Events | Sandbox, GUI, Katalog-Cache | 3 |
| `api` | FastAPI + WebSocket auf 127.0.0.1 mit Token, liefert das vorgebaute Frontend aus | geplant | Fachlogik | 4 |
| `ai` | Optionale Provider (lokal, API, Agenten-CLI), standardmäßig nicht importiert | geplant | Ausführen von Ergebnissen | 6 |
| `terminal` | Eingebettetes Terminal (PTY) | geplant | – | 7 |

## Ausführungspfad (Phase 3)

`wts run` → `load_workflow_file` (nichts wird ausgeführt) → `Runner.prepare` (Variablen, alle Tools auflösen, Gefahrenklasse je Schritt) → Planübersicht und Bestätigung (10.6) → `Runner.run` (je Schritt: Templates rendern → `build_argv` → Bestätigung bei caution/dangerous → `subproc.run_limited` mit Live-Chunks → Evaluatoren/Fehlerbehandlung). Vorschau/Beispiele laufen ausschließlich über `sandbox.run_sandboxed` in `bwrap`.

## Modell-Invarianten (Kurzfassung, Details in `FORMATS.md`)

- Jedes Dokument trägt `schema_version`; `migrate` hebt ältere Versionen an, bevor validiert wird.
- Unbekannte Felder sind Fehler (`extra="forbid"`), damit Tippfehler von Menschen und KI auffallen.
- Workflow = strukturierter Baum. Kanten für den Knoten-Graph werden abgeleitet, nie gespeichert. `layout` ist optional und trägt nur Positionen.
- Referenzen (`stdin.pipe`, `condition.source`, `{{ … }}`) zeigen nur auf sichtbare frühere Schritte, deklarierte Variablen oder umschließende `foreach`-Namen.
- Pfade in Modulen sind relativ und ohne `..`; `tool`-Namen sind keine Pfade.

## Tests

`tests/unit/` je Paket. `tests/corpus/` hält 29 echte Hilfetexte mit per Hand erstellten `expected.json`; `test_corpus.py` misst Options-Recall (Schwelle 90 % gesamt, 75 % je Tool), Typtreue (90 %) und Subbefehl-Recall (90 %). Neue Parserfehler werden zuerst dort als Fall angelegt. Drift-Test stellt sicher, dass `schemas/` zum Code passt.
