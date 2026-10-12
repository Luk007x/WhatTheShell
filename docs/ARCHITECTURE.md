# Architektur

Stand: Phase 0. Pakete, die noch nicht existieren, sind als „geplant" markiert und tragen den Phasenbezug aus dem Projektauftrag (Abschnitt 16).

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
| `cli` | `wts`-Einstieg, argparse-Subcommands | `main(argv) -> int` | Fachlogik; ruft nur Paketfunktionen | 0 |
| `catalog` | PATH durchsuchen, Hilfe lazy holen, Cache nach `path + version + help_hash` | geplant | Parsen der Hilfe | 1 |
| `helpparse` | Hilfetext → `CommandSpec` mit Konfidenz, Fallback „Freie Argumente" | geplant | Prozessstart, Cache | 1 |
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

`tests/unit/` je Paket. Ab Phase 1 `tests/corpus/` mit Golden Files echter Hilfetexte (Parser wird test-first gebaut). Drift-Test stellt sicher, dass `schemas/` zum Code passt.
