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

## D-009 GUI-Stack (Phase 4), 2026-10-12

- **Knoten-Graph: React Flow (`@xyflow/react`)**. Gründe: größte Verbreitung und Doku unter den Graph-Bibliotheken, MIT-Lizenz, eigene Node-Komponenten in React (Formulare direkt im Knoten oder im Seitenpanel), Ports/Handles für `then`/`else`/`body`/`pipe`, aktive Pflege. Svelte Flow wäre gleichwertig, React hat die breitere Bibliothekslandschaft (Blockly-Anbindung in Phase 5). Rete.js ist mächtiger, aber schwerer und auf Daten-Flow-Editoren ausgelegt.
- **Vite + React + TypeScript strict**, Layout mit `@dagrejs/dagre` wenn `layout` fehlt. Keine UI-Komponentenbibliothek, kein Tailwind: wenige handgeschriebene CSS-Regeln (Ponytail; Phase 5 kann nachlegen).
- **Typen aus den Schemas** generiert (`json-schema-to-typescript`), damit Kern und GUI dieselbe Wahrheit haben.
- **i18n** als 30-Zeilen-`t()` mit `de`/`en`-Wörterbüchern statt i18next; Umstieg möglich, wenn Pluralformen oder Formatierung nötig werden.
- **Backend FastAPI + uvicorn**, Runner im Thread, Events über asyncio-Queue an den WebSocket. Token im URL-Fragment, Header `X-WTS-Token`; Host- und Origin-Prüfung in einer Middleware (`docs/API.md`).
- **Frontend-Build wird nicht committet.** `wts gui` meldet klar, wenn `api/static/` fehlt. Phase 5 baut es in der CI und legt es ins Wheel.

### D-009 Ergänzungen nach API-Review, 2026-10-12

- **Die API fragt nie unbekannte Subbefehle per `--help` ab** (`probe_unknown=False` überall in `api/`). Subbefehl-Wörter müssen dem Muster aus `CommandStep.command` genügen. Grund: `GET /api/tools/sh?sub=-c/…` führte Code aus (Review-Befund). Nur `wts inspect` darf auf ausdrücklichen Nutzerwunsch abfragen.
- **Browserstart über eine Weiterleitungsdatei (0600)** mit `file://`-URL statt der Token-URL in der Kommandozeile von `xdg-open`/Browser, damit das Token nicht in `/proc/*/cmdline` steht (wie Jupyter).
- **Socket wird im CLI gebunden** und an uvicorn übergeben: kein Port-Race, kein Browserstart auf einen fremden Dienst.
- **Limits:** Body 1 MiB, Vorschau höchstens 2 parallel, höchstens 4 laufende und 20 vorbereitete Läufe, Event-Verlauf 10 000, `ws_max_size` 1 MiB, kein Access-Log (Token in der WebSocket-Query).
- **Bekannte Grenzen:** Jeder Tab desselben Nutzers kann Bestätigungen beantworten; die erste URL mit `#token` steht im Browserverlauf (Token gilt nur für die Sitzung).
- **Geplant (Phase 5):** Hilfe-Abruf generell in der bwrap-Sandbox ausführen, wenn sie verfügbar ist. Dann wäre auch das Abfragen unbekannter Subbefehle vertretbar.

## D-010 Phase 5: Block-Ansicht, Modul-Editor, Paketierung, 2026-10-12

- **Block-Ansicht als eigene React-Komponente statt Blockly** (Projektauftrag 11 und 16 nennen „Blockly o. ä."). Gründe: Die Baustein-Formulare sind je Tool dynamisch (Katalog + Modul), Blockly bräuchte dafür ein umfangreiches Mutator-/Feldsystem und eine zweite Abbildung Dokument ↔ Blockly-Workspace mit eigener Serialisierung; das Umschalten wäre damit eine Übersetzungsleistung mit Fehlerpotenzial. Die eigene Ansicht rendert dieselbe Schrittfolge verschachtelt (if/foreach/fallback als Container), nutzt exakt die Operationen aus `gui/src/model/ops.ts` (einrasten = `moveStep`) und teilt das Formular im rechten Panel. Verlustfreiheit ist damit per Konstruktion gegeben; die Datei ändert sich beim Umschalten nicht (auch `layout` bleibt unangetastet, da die Block-Ansicht keine Positionen braucht). Bundle bleibt klein. Wechsel zu Blockly bleibt möglich, falls echte Scratch-Interaktion (Puzzle-Formen) gewünscht wird.
- **Drag & Drop in der Block-Ansicht über natives HTML5-DnD**, dazu Tastatur-Aktionen (nach oben/unten, hinein/heraus) als gleichwertiger Weg (Barrierefreiheit). Keine DnD-Bibliothek.
- **Modul-Editor in der App** schreibt nur in den Nutzerordner (`~/.config/whattheshell/modules`), nie in mitgelieferte Dateien; Rohtext und Formular arbeiten auf derselben YAML-Datei, Validierung über die bestehende Loader-Logik; Export/Import als Datei über den Browser.
- **Übersetzungen aus Modulen** (`i18n.<lang>`) wendet der Server bei `GET /api/tools/{name}?lang=` auf Labels, Hilfetexte und Summary an; die GUI übergibt ihre Sprache. Englisch ist Fallback auf die Originaltexte.
- **Paketierung:** Die CI baut das Frontend und legt `api/static` ins Wheel (`hatch` force-include). Ein Release-Workflow erzeugt bei Tags das Wheel als Artefakt; veröffentlichen tut der Auftraggeber. Ein CI-Job installiert das Wheel mit `pipx` in einem frischen Schritt ohne Node und prüft `wts --version` und den Serverstart.
- **Hilfe-Abruf läuft in der bwrap-Sandbox**, wenn der Selbsttest sie freigibt (geplant seit D-009). Ohne Sandbox wie bisher auf dem Host mit Denylist. Liegt das Tool unter einem in der Sandbox verborgenen Präfix (`/home`, `/root`, `/tmp`, `/var/tmp`, `/run`) oder liefert die Sandbox keinen brauchbaren Text, folgt ein zweiter Durchlauf auf dem Host (Denylist gilt weiter); Ergebnisse mit `source=fallback` werden nie gecacht.

## D-011 KI-Funktionen (Phase 6), 2026-10-12

- **Schalter aus, Gate ohne Import:** `ai/__init__.py` importiert weder Provider noch `urllib`/`socket`/`subprocess`. Jeder Einstieg prüft `require_enabled` vor dem lazy Import der Provider. Der Test patcht `socket`/`subprocess` auf Fehler und prüft `sys.modules`.
- **Nur Stdlib für HTTP** (`urllib.request`) statt SDKs von Anthropic/OpenAI: zwei kleine JSON-Aufrufe, keine Abhängigkeit, kein Hintergrundverhalten.
- **Agenten-CLIs, Aufrufsyntax aus offizieller Doku (Stand 2026-10-12):**
  - Claude Code (code.claude.com/docs/en/cli-reference, …/headless): `["claude","-p","--output-format","text","--tools","","--permission-mode","dontAsk","--no-session-persistence","--system-prompt",SYSTEM,"--strict-mcp-config","--setting-sources","","--disable-slash-commands"]`, Prompt über stdin. Wirkung (`claude --help` lokal geprüft): `--tools ""` entfernt alle eingebauten Werkzeuge; `--strict-mcp-config` ohne `--mcp-config` lädt keine MCP-Server; `--setting-sources ""` lädt keine Nutzer-/Projekt-/lokalen Settings (Hooks, Allow-Regeln); `--disable-slash-commands` schaltet Skills ab. Plugins und Login-Daten des Kontos bleiben (Restrisiko, SECURITY.md 5).
  - Codex (developers.openai.com/codex/noninteractive, …/cli/reference): `["codex","exec","--sandbox","read-only","--skip-git-repo-check","--ephemeral","--color","never","-c","mcp_servers={}","-C",TMP,"-o",TMP/"last.txt","-"]`, Prompt über stdin; Antwort aus `last.txt`. `--sandbox read-only` erlaubt Lesezugriff auf die ganze Platte; `-c mcp_servers={}` nach Doku (Codex lokal nicht installiert, ungeprüft). `-a never` ist für `exec` nicht belegt und wird weggelassen.
  - Beide laufen mit `cwd` = leeres Temp-Verzeichnis und (seit D-012) eigenem temporärem `HOME`, in das nur die Anmeldedatei kopiert wird; bereinigte Umgebung plus `PATH` und Proxy-Variablen, `subproc.run_limited` mit Timeout und Ausgabelimit. Die Aufrufzeilen sind in `settings.yaml` (`ai.agent.command`) überschreibbar, weil sich CLIs ändern (F-28).
- **Schlüssel** nur aus Umgebungsvariable (`key_env`) oder Schlüsselbund (`keyring`, optionales Extra `whattheshell[keyring]`, lazy import), nie in Dateien.
- **Ergebnisse sind Dateien:** YAML aus der Antwort extrahiert, über den normalen Lader validiert, als Diff gezeigt, nur nach Freigabe in den Nutzerordner geschrieben; `diagnose` liefert reinen Text. Nichts wird ausgeführt.
- **Datenvorschau** vor jedem Senden; Befehlsausgaben nur mit `--include-output` bzw. `send_outputs`; Secrets maskiert.

## D-012 Verbesserungsrunde nach Phase 6 (Anmerkungen des Auftraggebers), 2026-10-12

- **KI-Preflight:** `wts ai check` und `GET /api/ai/check` prüfen die konfigurierte Quelle wirklich: lokal → Endpunkt erreichbar, Modell in `/models` vorhanden; API → Schlüssel gesetzt, optional ein Testaufruf; Agenten-CLI → Programm installiert, Version, Anmeldestatus (`claude auth status`, `codex login status` nach Doku). Fehlt etwas, nennt die Meldung den konkreten nächsten Schritt.
- **Agenten-CLIs laufen mit eigenem temporärem HOME:** nur die Anmeldedaten werden hineinkopiert (`~/.claude/.credentials.json` bzw. `~/.codex/auth.json`, 0600); kein globales `CLAUDE.md`, keine Settings, Hooks, Plugins oder `config.toml` des Nutzers wirken; nach dem Aufruf wird das Temp-HOME samt Sitzungsdateien gelöscht. Prompts sind auf Rolle, Eingabe und exaktes Ausgabeformat reduziert.
- **Ports am Knoten nur nach Schrittart:** jeder Schritt `in`/`next`; `if` zusätzlich `then`/`else`; `foreach` `body`; Fallback `fallback`; nur `command` hat `stdin`/`stdout`. Ports sind beschriftet, Kanten unterscheiden Ablauf (durchgezogen) und Daten (gestrichelt, „stdout → stdin"). Eine Legende und ein Hilfetext erklären, was fließt: die aufgezeichnete Textausgabe eines Schritts als Eingabe des nächsten; alle anderen Übergaben per `{{ schritt.stdout }}` in Feldern.
- **Design-System:** CSS-Variablen für Abstände, Farben (hell und dunkel per `prefers-color-scheme`), Radien, Schatten, Typografie; einheitliche Buttons, Felder, Panelköpfe; kein Überlappen (Grid mit Mindestbreiten, Umbruch in Toolbars). Weiterhin ohne UI-Bibliothek.
- **Workflow-Bibliothek und Ausführen-Modus:** Workflows werden aus festen Ordnern indexiert (mitgeliefert, `~/.config/whattheshell/workflows`, projektlokal `.whattheshell/workflows`) und live nachgeladen; die GUI hat die Modi „Erstellen" (Editor) und „Ausführen" (Liste, Eingabeformular aus `variables`, Bestätigung, Live-Ausgabe, Verlauf der letzten Läufe). Dateidialoge entfallen.

## D-013 Bedienung: Theme-Umschalter, Drag & Drop, Tastenkürzel, 2026-10-13

Rückmeldung des Auftraggebers nach der Verbesserungsrunde: kein Knopf für System/Hell/Dunkel (es gab nur `prefers-color-scheme`), Wunsch nach Maus- und Tastaturbedienung.

- **Theme:** `gui/src/theme.ts` löst „system" per `matchMedia` auf und setzt `html[data-theme]`; CSS kennt nur noch `:root[data-theme="dark"]`, kein Media-Query. Wahl in `localStorage("wts.theme")`, Knopf in der Kopfzeile (system → hell → dunkel), xyflow bekommt denselben Wert als `colorMode`.
- **Drag & Drop:** Katalog-Einträge und Kontrollbausteine sind `draggable` (eigene MIME-Typen `application/x-wts-tool`, `-kind`); der Drop auf der Fläche hängt den Schritt an das gewählte Ziel und speichert die Drop-Position im `layout`. Fremde Drops werden ignoriert, Tool-Namen gegen den Katalog geprüft (Daten aus anderen Tabs sind untrusted).
- **Kürzel** (nur im Modus „Erstellen", nicht in Feldern oder Dialogen): Entf/Rücktaste löschen die Auswahl (xyflow `deleteKeyCode`, Dialoge mit `nokey`), Strg+Z/Umschalt+Z/Y, Strg+S, Esc, Strg+Enter im Katalog, `?` öffnet die Kürzel-Übersicht. Enter im Katalog bleibt reines Auswählen, damit Tastaturnutzer nicht versehentlich Schritte anlegen.

## D-014 Phase 7 Sicherheitsabschnitt, 2026-10-13

Status: **freigegeben** am 2026-10-13 mit den Antworten kein Host-Terminal, Transkript Opt-in (Standard aus), höchstens 4 Terminals, kein Reattach (Projektauftrag 6.8 F-36, 16). Inhalt in `docs/SECURITY.md` Abschnitt 7.

- **Terminal nur in bwrap** mit den Argumenten von `build_bwrap_argv` und `prlimit` wie die Vorschau, plus PTY; ohne bwrap kein Terminal. Netz nur per `network: true` (hebt auf `caution`). Ein Host-Terminal ohne Sandbox entfällt in Phase 7.
- **Sitzung:** ein PTY-Prozess je Terminal-Schritt, WebSocket unter `/ws/` (Token, Host, Origin aus `SecurityMiddleware`), eine Verbindung je Terminal, höchstens 4, Idle- und harter Timeout, Trennung beendet die Prozessgruppe, kein Reattach.
- **Keine Protokollierung von Tastatureingaben**; Transkript nur der Ausgabe als Opt-in je Lauf, maskiert, 0600 unter `cache_dir()`.
- **`TerminalStep` (`kind: terminal`)** ohne `stdin`, Exit-Code steuert den Ablauf, Ausgabe wird nicht an Folgeschritte gereicht; CLI `wts run` lehnt Terminal-Schritte ab.
- **Abhängigkeit** `@xterm/xterm` (MIT), Backend nur Stdlib plus `setsid` (util-linux). Antworten des Auftraggebers in SECURITY.md 7.8.
