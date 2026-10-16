# WhatTheShell – Regeln für Claude Code

Grafischer Baukasten für Terminal-Workflows. Verbindlich: `PROJEKTAUFTRAG.md`
(Abschnitte 10, 13, 14 sind nicht verhandelbar). Abweichungen nur mit Eintrag in `docs/DECISIONS.md`.

## Arbeitsweise: Manager und Subagenten

Die Hauptsession ist **Manager**, nicht Umsetzer. Sie liest Contracts und Berichte, schneidet
Aufträge, delegiert, prüft. Produktivcode wird in der Hauptsession nicht geschrieben.

| Auftrag | Agent | Modell |
|---|---|---|
| Suchen, lesen, verorten | `Explore` | Haiku 5.5 |
| Tests, Linter, Typecheck ausführen | `test-runner` | Haiku 5.5 |
| Umsetzung mit festem Contract | `impl-python`, `impl-typescript` | Sonnet 5.5 |
| Reuse-Urteil, Review | `reuse-auditor`, `code-reviewer` | Sonnet 5.5 |
| Architektur, unklare Ursache, Hilfe-Parser-Heuristiken | `general-purpose` mit `model: opus` | Opus 5.5 (Ausnahme) |

Opus in einem Subagenten heißt fast immer: Auftrag zu offen. Erst schärfen, dann Modell vergrößern.

**Loop je Auftrag** (verbindliche Reihenfolge):

1. Auftragskarte schreiben (Skill `delegations-plan`): AGENT, DATEIEN, REIN, RAUS, ABBRUCH. Fehlt ein Feld, ist der Auftrag nicht vergabereif.
2. Ab Phase 1: `reuse-auditor` → Urteil WIEDERVERWENDEN | ERWEITERN | NEU, im Wortlaut in die Karte.
3. `impl-*` setzt genau die Karte um, nicht mehr.
4. `test-runner`, dann `code-reviewer`. BLOCKER → zurück an `impl-*`, nicht selbst nachbessern.
5. `docs/ARCHITECTURE.md` nachziehen, wenn sich eine öffentliche Schnittstelle oder ein Modulzweck geändert hat.

Aus Agentenberichten kommen nur **Öffentliche Schnittstelle** und **Offen** in den Hauptkontext.
Unabhängige Aufträge laufen parallel, abhängige nacheinander. Ein Auftrag berührt genau ein Modul.

**Phasen** (Projektauftrag Abschnitt 16): Zu Phasenbeginn Delegationsplan vorlegen, am Phasenende
Abnahmebericht (funktioniert / funktioniert nicht / offen / wie ausprobieren). Nächste Phase erst nach Freigabe.

## Ponytail und graphify

- **Ponytail** (Level `full`) gilt für jeden Auftrag: YAGNI, Stdlib vor Eigenbau, kürzester funktionierender Diff.
  Bewusste Abkürzungen mit `# ponytail: <Grenze>, <Ausbaupfad>` markieren. Nie wegkürzen: Validierung an
  Vertrauensgrenzen, Fehlerbehandlung, Sicherheit (Abschnitt 10), Barrierefreiheit, explizit Beauftragtes.
- **graphify** (`/graphify`): nach jeder Phase den Graphen über `src/`, `gui/src/` und `docs/` neu bauen.
  Fragen zur Codebasis zuerst als graphify-Query stellen, erst dann `Explore`.

## Sicherheit (Kurzfassung von Abschnitt 10, keine Ausnahmen)

- Nie `shell=True`, nie String-Konkatenation von Befehlen. Immer `argv`-Liste. Anzeige nur per `shlex.quote`.
- Nie Befehle aus Dateien beim Laden ausführen. Workflow-Dateien sind untrusted.
- Vorschau ausschließlich in `bwrap`. Kein ungeschützter Ersatzmodus.
- Web-API nur `127.0.0.1`, Sitzungstoken, Origin-/Host-Prüfung, kein CORS, kein root.
- KI-Code-Pfad bei ausgeschalteter KI nicht erreichbar. KI-Ausgaben sind untrusted, nur Diff zur Freigabe.
- Felder vom Typ `secret` werden in Logs maskiert.

## Konventionen

- Python ≥ 3.11, `uv` für Umgebung und Lockfile. Type Hints überall, `mypy --strict`, `ruff` (Lint + Format), `pytest`.
- TypeScript strict, kein `any`, kein `@ts-ignore`. Typen aus dem Modell ableiten, nicht doppelt pflegen.
- Eine Quelle der Wahrheit: Pydantic-Modelle in `src/whattheshell/models/`, Schemas nach `schemas/` generiert, nie von Hand.
- Kern ohne GUI-Abhängigkeit, alles per CLI testbar.
- Fehler nie verschlucken: Meldung mit Ursache und Lösungshinweis.
- Keine neue Abhängigkeit ohne Eintrag in `docs/DEPENDENCIES.md` (Lizenz prüfen, AGPL-kompatibel).
- Sprache: Code, Bezeichner, Commit-Messages Englisch. Docs und UI-Standardsprache Deutsch, UI i18n ab Anfang.
- Projektname steht genau einmal: `pyproject.toml` plus eine Konstante.
- Commits klein, je abgeschlossener Auftragskarte. Kein Commit ohne grünen `test-runner`. Remote: `origin` auf GitHub, Push am Phasenende.
- Lizenz: Code AGPL-3.0-or-later (SPDX-Header in jeder Quelldatei), mitgelieferte Module/Workflows CC0-1.0.

## Befehle (ab Phase 0)

```
uv sync --all-extras          # Umgebung
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest
uv run wts --help             # CLI: tools, inspect, validate, scaffold, modules, workflows, sandbox, example, run, gui, ai (check/status/…), schema export
cd gui && npm ci && npm run build && npm run typecheck && npm test   # Frontend; npm run e2e = Playwright-Smoke gegen wts gui
```

## Struktur

```
src/whattheshell/{catalog,helpparse,models,modules,subproc.py,paths.py,engine,sandbox,safety,api,ai,cli.py}
src/whattheshell/bundled/{modules,workflows}/   mitgelieferte Module und Workflows (CC0), landen so im Wheel
gui/            TypeScript-Frontend, Build nach src/whattheshell/api/static/
schemas/        generierte JSON-Schemas
docs/           ARCHITECTURE.md, DECISIONS.md, FORMATS.md, MODULE_AUTHORING.md, SECURITY.md, DEPENDENCIES.md, BACKLOG.md, RELEASING.md
tests/          unit/, corpus/ (29 echte Hilfetexte + expected.json, Schwelle 90 % Recall), e2e/
```

`docs/ARCHITECTURE.md` listet jedes Paket mit Zweck, öffentlicher Schnittstelle und „nicht zuständig für" in wenigen Zeilen.
