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

## D-006 Katalog und Hilfe-Parser (Phase 1), 2026-10-12

- **Cache-Schlüssel** `path + mtime_ns + size` statt `path + version + help_hash` (F-4). Version und Hilfe-Hash kosten je einen Prozessstart; mtime/size erkennen ein Tool-Update ebenso. `version` und `help_hash` werden trotzdem im Eintrag gespeichert.
- **Annahme:** Ein Tool behandelt `--help` und `-h` harmlos. Für bekannte Ausnahmen gibt es die Denylist `NEVER_PROBE` (shutdown, reboot, halt, poweroff, init, telinit, kexec), geprüft gegen Basisname und aufgelösten Symlink. Jeder Hilfe-Abruf läuft über `subproc.run_limited`: eigene Prozessgruppe, Timeout 5 s, 1 MB Ausgabelimit, bereinigte Umgebung, stdin geschlossen.
- `fetch_help` liegt im Paket `catalog`, nicht in `helpparse`: der Parser bleibt reine Textverarbeitung und ohne Prozessstart testbar.
- **Korpus:** 29 Tools statt der Liste aus Abschnitt 9: docker → podman (gleiches cobra-Format), awk → gawk, dazu bat/uv (clap), gh (cobra), pip/json.tool (argparse), ssh und ip (nur Usage), `man grep`. BusyBox und ein click-basiertes Tool sind auf dem Entwicklungssystem nicht installiert und fehlen noch.
- Interaktive Programme werden über eine feste Liste erkannt (`INTERACTIVE`), Module können das in Phase 2 überschreiben.

## D-007 Module (Phase 2), 2026-10-12

- **Mitgelieferte Module und Workflows liegen in `src/whattheshell/bundled/`**, nicht wie in Abschnitt 12 im Wurzelverzeichnis. Grund: nur so landen sie ohne Sonderregeln im Wheel (`pip`/`pipx`). Lizenz CC0 bleibt je Ordner.
- **`inputs` im Modul ersetzen die Katalog-Eingaben**, `options` mergen nach id (FORMATS §6). Katalog-Eingabe-ids kollidierten mit Options-ids (find `path`), und umbenannte Modul-Eingaben standen doppelt daneben.
- **Hot-Reload mit `watchfiles`** (MIT), wie im Projektauftrag erlaubt. Kein eigener Poller.
- **Cache bleibt roh**: Module werden bei jedem `Catalog.get` nach dem Cache angewandt, damit eine Moduländerung ohne Cache-Invalidierung sichtbar ist.
- **Offen für Phase 3:** Optionen mit mehreren Werten je Vorkommen (jq `--arg name value`) kennt `OptionSpec` nicht (`nargs`). Entscheidung beim argv-Aufbau der Engine.
- Beispiele der mitgelieferten Module sind bis Phase 3 nur schema-validiert, nicht ausgeführt. Ab Phase 3 läuft jedes Beispiel in der Sandbox als Test.
- **Lokaler Python-Pin `.python-version` = 3.12.** uv hatte ohne Pin den Free-Threading-Build 3.14t gewählt. Die CI prüft weiter 3.11 bis 3.14; lokal gilt ein GIL-Build, damit Thread-Verhalten (Registry, Watcher) dem Normalfall entspricht.

## D-008 Engine, Sicherheit, Sandbox (Phase 3), 2026-10-12

- **Pipes sind aufgezeichnete Ausgaben**, keine gleichzeitig laufenden Prozesse: `stdin.pipe` übergibt die gespeicherte stdout des Vorgängers (bis zum Ausgabelimit). Einfacher, deterministisch, Live-Ausgabe je Schritt bleibt. Echte Streaming-Pipes erst, wenn ein Anwendungsfall sie braucht.
- **Gefahrenklasse zweimal**: beim Vorbereiten (für Plan und Übersicht) und noch einmal zur Laufzeit auf den gerenderten Werten; es gilt das Maximum. Grund: Templates (`--var`, Schleifenwerte, Tool-Ausgaben) könnten sonst `--delete` nachschieben (Review-Befund).
- **Hilfe-Abruf nur für bekannte Subbefehle**: `Catalog.get(tool, command)` fragt `tool sub --help` nur ab, wenn `sub` im Elternbefehl (Katalog oder Modul) bekannt ist; sonst Fallback ohne Prozessstart. Grund: Eine fremde Workflow-Datei konnte sonst beim `--dry-run` über `sh -c` Code starten (Review-Befund). `wts inspect` darf unbekannte Subbefehle abfragen, weil der Nutzer sie selbst eintippt.
- **`env`, fremdes `cwd`, `stdin.file` heben auf `caution`** und erscheinen im Bestätigungstext. Eine Sperrliste für Umgebungsvariablen bleibt zweite Linie, weil eine Allowlist echte Workflows bricht.
- **Speicher- und Prozesslimit in der Sandbox über `prlimit`** innerhalb von bwrap statt `preexec_fn` (Fork-Risiko im Mehrthread-Prozess). Fester `PATH` in der Sandbox.
- **Bestätigung je Schleifeniteration** bleibt vorerst; eine „für alle Iterationen"-Antwort ist eine GUI-Aufgabe (Phase 4).
- **Unbekannte Tools gelten als `safe`** (Basis aus Katalog), bekannte Wrapper und Interpreter (`timeout`, `busybox`, `awk`, `nc`, `socat`, …) als `caution`. Offen: fremde Workflows generell strenger einstufen (GUI-Entscheidung, Phase 4).
- Reguläre Ausdrücke aus Dateien laufen nur auf Texten bis zum Ausgabelimit (1 MiB); katastrophales Backtracking ist damit begrenzt, nicht ausgeschlossen.
