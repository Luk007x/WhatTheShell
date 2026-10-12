# Architektur

Stand: Phase 6 plus Verbesserungsrunde (D-012). Pakete, die noch nicht existieren, sind als „geplant" markiert und tragen den Phasenbezug aus dem Projektauftrag (Abschnitt 16).

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
| `cli` | `wts`-Einstieg, argparse-Subcommands (`schema export`, `tools`, `inspect`, `validate`, `scaffold`, `modules`, `run`, `example`, `sandbox`, `gui`) | `main(argv) -> int` | Fachlogik; ruft nur Paketfunktionen | 0 |
| `subproc` | Begrenzter Prozessstart: argv, eigene Prozessgruppe, Timeout, Byte-Limit, bereinigte Umgebung | `run_limited`, `sanitized_env` | Entscheidung, was gestartet wird | 1 |
| `catalog` | PATH durchsuchen, Hilfe lazy holen (`--help`, `-h`, `man`; Hilfe-Abruf in bwrap, wenn verfügbar), Cache nach `path + mtime + size` (innen `help_hash`, `version`), Subbefehle mit Tiefenlimit, interaktive Tools markieren, Modul-Overrides nach dem Cache anwenden (`Catalog(registry=…)`) | `scan_path`, `Catalog.tools/get`, `fetch_help`, `ToolNotFound`, `INTERACTIVE`, `NEVER_PROBE` | Parsen der Hilfe | 1 |
| `helpparse` | Reiner Text → `CommandSpec` mit Konfidenz je Option, Fallback „Freie Argumente" (`raw_help`); Golden-Korpus in `tests/corpus/` | `parse_help`, `clean_text` | Prozessstart, Cache | 1 |
| `paths` | XDG-Verzeichnisse und Modul-Suchpfade | `cache_dir`, `config_dir`, `module_dirs` | – | 1 |
| `workflows` | Workflow-Index über mitgelieferte, Nutzer- und Projektordner mit Live-Reload, Shadowing nach Priorität, Fehler je Datei isoliert | `WorkflowIndex`, `WorkflowEntry` | Ausführen, Schreiben (macht `modules.store`) | V |
| `settings` | `settings.yaml` im Config-Ordner (nur `ai`-Block, keine Schlüssel), atomar schreiben | `Settings`, `load_settings`, `save_settings`, `settings_path` | – | 6 |
| `modules` | Modul-/Workflow-Dateien laden mit Zeilennummern, Registry über Suchpfade mit isolierten Fehlern, Merge nach FORMATS §6, Hot-Reload (`watchfiles`), Modul-Gerüst, Übersetzungen aus `i18n` anwenden | `load_document`, `load_module_file`, `load_workflow_file`, `DocumentError`, `ModuleRegistry`, `LoadedModule`, `apply_modules`, `merge_command`, `watch_modules`, `scaffold_module`, `translate_command` | Ausführen, Katalog-Cache | 2 |
| `bundled` | Mitgelieferte Module und Workflows als Paketdaten | `MODULES_DIR`, `WORKFLOWS_DIR` | – | 2 |
| `safety` | Gefahrenklasse je Befehl und Option: Basis aus Katalog/Modul, Tool-Listen, Flag-Muster, `extra_args` | `classify_command`, `Verdict`, `summarize`, `needs_confirmation` | Ausführung, Prozesse | 3 |
| `sandbox` | `bwrap`-Aufruf (ro-root, tmpfs für /home /tmp /run, `--unshare-all`, `--clearenv`, Workdir unter `/tmp/work`), Selbsttest mit Distro-Hinweis, Zeit-/Speicher-/Ausgabelimit, Beispiel-Läufer | `self_test`, `SandboxStatus`, `run_sandboxed`, `build_bwrap_argv`, `run_example`, `iter_examples` | Entscheidung, was ausgeführt wird; Fallback ohne bwrap (gibt es nicht) | 3 |
| `engine` | argv-Aufbau aus Spec + args (nie Shell), Templates (`{{ }}`, eingeschränkt), Evaluatoren, Runner (Schritte, Pipe als aufgezeichnete Ausgabe, if/foreach/set/wait/message/abort, on_error, Bestätigung, Maskierung, env-Sperrliste, Events, Controller mit Abbruch/Pause/Einzelschritt), Plan (Dry-Run) | `build_argv`, `render`, `evaluate`, `Runner.prepare/run`, `plan`, `plan_text`, `Controller`, Events | Sandbox, GUI, Katalog-Cache | 3 |
| `api` | FastAPI auf 127.0.0.1: Sicherheits-Middleware (Host, Origin, Token, Body-Limit), REST für Status/Tools (mit `lang`)/Module (Liste, Editor-Endpunkte, Gerüst)/Vorlagen/Befehl/Vorschau/Workflows, Lauf-Manager mit Thread, Events, Bestätigung, Steuerung und WebSocket; Modul-Watcher im Lifespan; liefert das gebaute Frontend aus | `create_app`, `Session`, `SecurityMiddleware`, `RunManager`, Router in `rest`, `workflows`, `runs`, `modules_api`, `settings_api`, `ai_api` (Gate vor jedem KI-Aufruf, zweiphasig Vorschau/Senden, `apply` nur in Nutzerordner) | Fachlogik (ruft Kern-Pakete), Hilfe-Abruf unbekannter Subbefehle (nie) | 4–5 |
| `gui/` (TypeScript) | Vite + React mit eigenem Design-System (Tokens, Dunkelmodus, Icons): Modi „Erstellen" (Katalog, Arbeitsfläche als Graph mit Ports je Schrittart oder Block-Ansicht, Formulare, Vorschau, Laufpanel, Datei-Menü mit Bibliothek), „Ausführen" (Bibliothek aus dem Index, Eingabeformular aus `variables`, Bestätigung, Live-Ausgabe, Verlauf; `run/useRun.ts` teilt die Lauf-Logik) und „Module" (Editor); Einstellungen inkl. KI; i18n de/en; Typen aus `schemas/`; Playwright-Suiten smoke, a11y (axe), ai, design (Überlappung, Screenshots), run | – | Eigene Fachlogik (nur Darstellung und Editieroperationen) | 4–6, V |
| `ai` | Optionale KI-Funktionen, Standard aus: Gate (`require_enabled`, kein Provider-Import vorher), Aufgaben (Modul verbessern, Beispiele, Workflow-Entwurf, Fehlerdiagnose) als Prompt-Bauer, YAML-Extraktion, Validierung über den normalen Lader, Diff, Freigabe nur in den Nutzerordner; Provider in `ai/providers` (OpenAI-kompatibel lokal/API, Anthropic, Agenten-CLIs `claude`/`codex` als Subprozess mit Temp-cwd) mit Stdlib-HTTP | `require_enabled`, `AiDisabled`, `make_provider`, `Prompt`, `Provider`, `tasks.*`, `approve.apply`, `diff.unified`, `providers.build`, `check.check` (Preflight: Endpunkt, Modell, Programm, Anmeldung) | Ausführen von Ergebnissen (nie), Speichern ohne Freigabe (nie), Schlüssel in Dateien (nie) | 6 |
| `terminal` | Eingebettetes Terminal (PTY) | geplant | – | 7 |

## Ausführungspfad (Phase 3)

`wts run` → `load_workflow_file` (nichts wird ausgeführt) → `Runner.prepare` (Variablen, alle Tools auflösen, Gefahrenklasse je Schritt) → Planübersicht und Bestätigung (10.6) → `Runner.run` (je Schritt: Templates rendern → `build_argv` → Bestätigung bei caution/dangerous → `subproc.run_limited` mit Live-Chunks → Evaluatoren/Fehlerbehandlung). Vorschau/Beispiele laufen ausschließlich über `sandbox.run_sandboxed` in `bwrap`.

## GUI-Pfad (Phase 4)

`wts gui` bindet einen Socket auf 127.0.0.1, erzeugt ein Sitzungstoken, öffnet den Browser über eine 0600-Weiterleitungsdatei und startet uvicorn. Die SPA hält das Token im Speicher und ruft die REST-Endpunkte auf; ein Lauf wird mit `POST /api/runs` vorbereitet (Plan, Klassen), nach Bestätigung gestartet und über `/ws/runs/{id}` live verfolgt; Bestätigungen für `caution`/`dangerous` laufen als Dialog über denselben Kanal. Der Zustand der GUI ist das Workflow-Dokument; der Knoten-Graph wird daraus berechnet (`toGraph`), Editieraktionen sind reine Operationen auf dem Dokument.

## Paketierung (Phase 5)

`scripts/build_wheel.sh` baut das Frontend (`gui/`) nach `src/whattheshell/api/static/` und danach Wheel und sdist; hatchling nimmt den Build über `artifacts` mit, obwohl er nicht in git liegt. Die CI baut das Wheel als Artefakt und installiert es in einem Node-freien Job per `pipx`; `release.yml` hängt es bei Tags `v*` an ein GitHub-Release. Veröffentlichung auf PyPI macht der Auftraggeber (`uv publish`).

## KI-Pfad (Phase 6)

`wts ai …` und `/api/ai/*` prüfen zuerst `settings.ai.enabled`; bei aus endet der Aufruf, bevor `ai.providers` importiert wird (Test: gepatchte `socket`/`subprocess` und `sys.modules`). Bei an: Prompt bauen → Datenvorschau (maskiert) → Freigabe zum Senden → Provider → YAML extrahieren → Lader validieren → Diff → Freigabe zum Schreiben → Nutzerordner. Nichts wird ausgeführt; `diagnose` liefert nur Text.

## Modell-Invarianten (Kurzfassung, Details in `FORMATS.md`)

- Jedes Dokument trägt `schema_version`; `migrate` hebt ältere Versionen an, bevor validiert wird.
- Unbekannte Felder sind Fehler (`extra="forbid"`), damit Tippfehler von Menschen und KI auffallen.
- Workflow = strukturierter Baum. Kanten für den Knoten-Graph werden abgeleitet, nie gespeichert. `layout` ist optional und trägt nur Positionen.
- Referenzen (`stdin.pipe`, `condition.source`, `{{ … }}`) zeigen nur auf sichtbare frühere Schritte, deklarierte Variablen oder umschließende `foreach`-Namen.
- Pfade in Modulen sind relativ und ohne `..`; `tool`-Namen sind keine Pfade.

## Tests

`tests/unit/` je Paket. `tests/corpus/` hält 29 echte Hilfetexte mit per Hand erstellten `expected.json`; `test_corpus.py` misst Options-Recall (Schwelle 90 % gesamt, 75 % je Tool), Typtreue (90 %) und Subbefehl-Recall (90 %). Neue Parserfehler werden zuerst dort als Fall angelegt. Drift-Test stellt sicher, dass `schemas/` zum Code passt.
