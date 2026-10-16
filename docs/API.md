# Lokale HTTP/WebSocket-API (Phase 4)

Verbindlicher Vertrag zwischen `src/whattheshell/api/` und `gui/`. Nur `127.0.0.1`, nur mit Sitzungstoken.

## Sicherheit (Projektauftrag Abschnitt 11)

- Server bindet an `127.0.0.1`, freier Port (oder `--port`). Start als root wird verweigert.
- Beim Start wird ein zufälliges Token (32 Byte, urlsafe) erzeugt. `wts gui` öffnet `http://127.0.0.1:PORT/#token=…`; die SPA liest das Fragment, hält es im Speicher und sendet es als Header `X-WTS-Token` bei jeder Anfrage. Beim WebSocket als Query `?token=…`.
- Jede Anfrage unter `/api/` und `/ws/` ohne gültiges Token → 401 `{"error": "token"}`.
- `Host` muss `127.0.0.1:PORT` oder `localhost:PORT` sein, sonst 400 (DNS-Rebinding).
- Bei Nicht-GET-Anfragen und WebSocket muss `Origin` (falls gesetzt) `http://127.0.0.1:PORT` oder `http://localhost:PORT` sein, sonst 403 (CSRF). Keine CORS-Header.
- Statische Dateien (`/`, `/assets/*`) ohne Token, aber mit Host-Prüfung.
- Limits: Anfragekörper max. 1 MiB (413), WebSocket-Nachrichten max. 1 MiB. `/api/preview` führt höchstens 2 Vorschauen gleichzeitig aus; Wartezeit über 15 s → 429. `command`-Wörter und `tool` in Anfragen folgen denselben Mustern wie bei `/api/tools` (422).
- Der Server loggt keine Zugriffe (`access_log=False`), damit das WebSocket-Token in der Query nicht im Log landet. `wts gui` öffnet den Browser über eine private Weiterleitungsdatei (`file://`, 0600), die Token-URL steht so nicht in der Prozessliste.
- Jeder Client mit gültigem Token (z. B. ein zweiter Tab) darf Bestätigungen beantworten; es ist derselbe Nutzer.
- Fehlerantworten: `{"error": "<kurz>", "message": "<deutsch, mit Hinweis>"}`.

## Sprache der Meldungen

Fehlertexte und Ereignisse folgen der Sprache der Anfrage. HTTP: Header `X-WTS-Lang: de|en` (sendet die GUI), sonst erster Wert von `Accept-Language`, sonst Umgebungsvariable `WTS_LANG` (überstimmt die gespeicherte Einstellung), Einstellung `language`, Systemsprache, `en`. WebSocket (Browser können dort keine Header setzen): Query `?lang=de|en`, sonst `Accept-Language`, sonst Standard. `lang` bei `/api/tools` und `/api/tools/{name}` (Modultexte) wählt ausdrücklich und hat Vorrang.

## REST (JSON, UTF-8)

| Methode, Pfad | Anfrage | Antwort |
|---|---|---|
| `GET /api/status` | – | `{app, version, sandbox: SandboxStatus, module_errors: [{path, line, message}], config_dir, workflows_dir, modules_watch: bool, workflows_watch: bool}` (`modules_watch`/`workflows_watch`: Hot-Reload der Modul- bzw. Workflowdateien läuft). Die Hilfe-Abfrage unbekannter Tools läuft in der Sandbox, sobald der erste Selbsttest sie als verfügbar meldet |
| `POST /api/shutdown` | – | 202 `{status: "stopping"}`; beendet den Server sauber (Terminals mit Close-Code 1001 schließen, Läufe abbrechen, Threads bis 5 s abwarten). Nur unter `wts gui`; sonst 503 `no_server`. Doppelaufruf harmlos. Tabs zu schließen beendet den Server nicht; dasselbe Herunterfahren läuft bei Strg+C und SIGTERM |
| `POST /api/sandbox/selftest` | – | `SandboxStatus` (erneut geprüft) |
| `GET /api/tools?search=&lang=de|en` | – | `[{name, path, interactive, display_name?, category?, summary?, safety?}]` (`interactive`: Standard false, true für Tools der `INTERACTIVE`-Menge, Modul-Override `interactive` hat Vorrang, gleiche Regel wie `ToolInfo.command.interactive`; Zusatzfelder nur aus geladenen Modulen, kein Hilfe-Abruf) |
| `GET /api/tools/{name}?sub=a/b&deep=0|1&refresh=0|1&lang=de|en` | – | `ToolInfo` (Modelle aus `schemas/`), `sub`-Wörter müssen `^[A-Za-z][A-Za-z0-9_-]*$` genügen (sonst 422), `name` dem Tool-Namensmuster. Unbekannte Subbefehle werden nicht abgefragt (kein Prozessstart): Fallback-Eintrag ohne Optionen. `lang` (Muster `^[a-z]{2,3}$`, Standard `de` = Originaltexte der Module): wendet `i18n[lang]` des Moduls auf `display_name`, `summary`, `description` sowie `label`/`help` von Optionen und Eingaben an (rekursiv); fehlt die Sprache oder ein Text, bleibt der Originaltext. Gleiches für `display_name`/`summary` in `GET /api/tools` |
| `GET /api/modules` | – | `{search_paths: [{dir, count, exists}], modules: [{priority, tool, path}], errors: [...]}` |
| `GET /api/modules/{tool}` | – | `{tool, source: "user"|"bundled", path, raw, document: Module|null, errors: [{path, line, message}], scaffold_available}`; Nutzerdatei (`config_dir()/modules/<tool>.module.yaml`) vor mitgelieferter; `document` ohne Standardwerte, `null` bei kaputter Datei (dann `errors`, `raw` bleibt); `scaffold_available` = Tool auf PATH. Kein Modul → 404 mit Hinweis auf `scaffold` |
| `PUT /api/modules/{tool}` | `{raw: str}` | Rohtext ist die Wahrheit: wird validiert (422 `validation` mit `errors: [{path, line, message}]`; `document.tool` ≠ `{tool}` → 422 `tool_mismatch`), atomar in die Nutzerdatei geschrieben, Registry neu geladen; Antwort `{tool, path}`. Mitgelieferte Module bleiben unberührt |
| `DELETE /api/modules/{tool}` | – | 204, löscht nur die Nutzerdatei (nur mitgeliefert → 403, sonst 404) und lädt die Registry neu |
| `POST /api/modules/scaffold` | `{tool, command: []}` | `{raw}`: Modul-Gerüst aus dem rohen Katalog (ohne Modul-Overrides, `Catalog` ohne Registry); 404 unbekanntes Tool, 422 bei ungültigen Wörtern |
| `GET /api/templates/{tool}` | – | `[{title, workflow: {id|null, document: Workflow|null}, error?}]`: `templates[]` aller Module des Tools, Pfad relativ zur Moduldatei (mitgelieferte Vorlagen liegen neben den Modulen), `id` = Dateiname ohne `.workflow.yaml`; unlesbare Vorlage → Eintrag mit `error` |
| `POST /api/command` | `{tool, command: [], args: {}, extra_args: []}` | `{argv: [], display, safety, reasons: []}` oder 422 mit `message` (ArgvError) |
| `POST /api/preview` | `{tool, command, args, extra_args, example: int|null, stdin: str|null}` | `{command, exit_code, stdout, stderr, duration, truncated, timed_out}`; Fixtures des gewählten Beispiels werden angelegt; 409 wenn Sandbox nicht verfügbar; nur in bwrap |
| `GET /api/workflows` | – | Workflow-Bibliothek: `[{id, name, description, source: "bundled"|"user"|"project", path, variables: {name: VariableSpec}, steps: int, error: str|null, shadows: [source], writable: bool, integrity: "ok"|"modified"|"unstamped"|"invalid"}]` (`integrity`: siehe FORMATS §8, `invalid` = `error` gesetzt; `writable`: false, wenn eine Projektdatei gewinnt). Suchordner in aufsteigender Priorität: mitgeliefert, `config_dir()/workflows`, `<cwd der App>/.whattheshell/workflows`; Endungen `.workflow.yaml|.yml|.json`, `id` = Dateiname ohne Endung. Es erscheint nur der Gewinner, `shadows` nennt die überdeckten Quellen. Kaputte Dateien erscheinen mit `error` (`Pfad:Zeile: Meldung`), `name` = id. Der Index wird live nachgeladen |
| `GET /api/workflows/{id}` | – | `{id, path, source, integrity, error, document: Workflow, raw: str}` des Gewinners |
| `PUT /api/workflows/{id}` | `{document: Workflow}` | validiert (422 mit `errors: [{path, message}]`), gewinnt eine Projektdatei, 409 `shadowed`; sonst schreibt YAML in den Nutzerordner (andere Quellen bleiben unberührt; die Nutzerdatei gleicher id überschattet mitgelieferte), lädt den Index neu, antwortet `{id, path}` |
| `DELETE /api/workflows/{id}` | – | 204 (löscht nur die Nutzerdatei; liegt die id nur in `bundled` oder `project`, 403 mit Hinweis; gewinnt eine Projektdatei, 409 `shadowed`; Projektdateien von Hand entfernen; unbekannt 404) |
| `POST /api/workflows/{id}/run` | `{variables: {}, cwd: str|null, dry_run: bool, transcript: bool=false}` | Abkürzung: lädt das Dokument des Gewinners aus dem Index und verhält sich wie `POST /api/runs` (gleiche Antwort und Fehler); unbekannte id 404. Ist `integrity` `modified` oder `unstamped` und kein `dry_run`: 409 `{error: "integrity", status: "modified"|"unstamped", message}` (erst `accept`). `POST /api/runs` mit einem Dokument im Body kennt keine Datei und prüft nichts |
| `POST /api/workflows/import` | `{filename, content, overwrite: bool=false}` | YAML-Text wie eine Datei prüfen und nach `config_dir()/workflows/<filename>` schreiben (gestempelt); `filename` = `id.workflow.yaml` ohne Pfad (sonst 400 `filename`), höchstens 1 MiB (413), ungültig 422 mit `errors: [{path, message}]` (nichts geschrieben), Datei vorhanden ohne `overwrite` 409 `exists`, Projektdatei gewinnt 409 `shadowed`; 201 mit dem Listeneintrag |
| `POST /api/workflows/{id}/accept` | – | prüft die aktuelle Datei erneut und stempelt sie (ungültig 422, unbekannt 404, mitgelieferte: nichts zu tun); antwortet mit dem Listeneintrag |
| `POST /api/workflows/validate` | `{document}` | `{ok, errors: [...]}` |
| `POST /api/runs` | `{document: Workflow, variables: {}, cwd: str|null, dry_run: bool, transcript: bool=false}` | `{run_id, plan: str, needs_confirmation: bool, max_safety}`; bei `dry_run` kein Lauf, nur Plan. `transcript: true` speichert die Programmausgabe von Terminal-Schritten (siehe „Terminal“). `prepare` läuft sofort (Tools auflösen, Klassen); Fehler → 422 |
| `GET /api/runs` | – | Gestartete Läufe, neueste zuerst, höchstens 50: `[{run_id, status, workflow_name, started, finished, exit_code}]` (ISO-8601, `finished`/`exit_code` null solange der Lauf läuft; nur im Speicher der App) |
| `POST /api/runs/{id}/start` | – | 202; startet den Lauf im Hintergrund (Workflow-Bestätigung nach 10.6 gilt mit diesem Aufruf als erteilt) |
| `GET /api/runs/{id}` | – | `{status, events: [...]}` (Verlauf, max 10 000 Events) |
| `POST /api/runs/{id}/control` | `{action: "abort"|"pause"|"resume"|"step"}` | 204 |
| `POST /api/runs/{id}/confirm` | `{step_id, ok: bool}` | 204 (Antwort auf `confirm_request`) |
| `POST /api/runs/{id}/answer` | `{step_id, values: {name: wert}, button}` oder `{step_id, cancel: true}` | 202 `{status: "answered"}` (Antwort auf `ask_request`); `404 {error: "no_question"}`, wenn für den Schritt nichts offen ist. Die API prüft nur die Form; Werte prüft der Runner und fragt bei Fehler mit `error` erneut |
| `GET /api/terminal/transcripts` | – | `[{name, size, mtime}]` (neueste zuerst; `mtime` Unix-Sekunden) aus `cache_dir()/terminal/` |
| `DELETE /api/terminal/transcripts/{name}` | – | 204; `name` muss `^[A-Za-z0-9._-]+\.txt$` sein, ohne führenden Punkt und Pfadanteil (sonst 422 `name`), unbekannt 404. CLI: `wts terminal transcripts [--delete NAME]` |
| `GET /api/settings` | – | Settings-Dokument (siehe unten) plus schreibgeschützte Felder `load_error: string|null` (Ladefehler der Datei; dann liefert die API Standardwerte) und `key_status: "set"|"missing"` (ist die Umgebungsvariable `ai.api.key_env` gesetzt; der Wert wird nie ausgegeben) |
| `PUT /api/settings` | Settings-Dokument (ohne `key_status`, `load_error`) | Validierung wie `Settings` (unbekannte oder Schlüsselfelder → 422 `validation`, ohne Eingabewerte), schreibt atomar (0600), lädt die Einstellungen neu; Antwort wie `GET`. `ai.enabled` wird nur hier oder mit `wts ai enable` true |
| `GET /api/ai/check?network=1\|0` | – | `{ok, provider, items: [{name, ok, detail, hint}]}`: Preflight der konfigurierten Quelle (D-012). Ohne Gate: bei ausgeschalteter KI trotzdem 200 mit dem einzigen Item „KI aus“ (`ok: false`), damit die GUI es anzeigen kann; Anbieter-, Netz- und Prozesscode wird dann nicht geladen. `network=0` kontaktiert keinen Endpunkt; Agenten-CLIs werden immer gestartet (`--version`, Anmeldestatus im Temp-HOME). Fehler und Zeitlimits sind Items, nie 5xx |
| `GET /api/ai/agents` | – | `{"claude": {"path": Pfad\|null, "models": [Name], "default": "", "reasoning": false}, "codex": {…, "reasoning": true}}`: `path` ist der absolute Pfad des Agenten-Programms auf PATH, sonst `null`; `models` eine statische Liste bekannter Modellnamen (leer = Freitext, z. B. Codex); `default` `""` = Standardmodell des Programms; `reasoning` zeigt, ob die Einstellung `ai.agent.reasoning` wirkt (nur Codex). Ohne Gate (auch bei ausgeschalteter KI 200), damit die GUI vor dem Einschalten den Anbieter wählen lässt. Prüft nur PATH: kein Prozess, kein Netz, keine Versions- oder Anmeldeprüfung |
| `POST /api/ai/improve-module` | `{tool, send: bool=false}` | siehe Abschnitt „KI-Endpunkte“ |
| `POST /api/ai/examples` | `{tool, send}` | dito |
| `POST /api/ai/draft-workflow` | `{description, name?, send}` | dito (`name` = Dateiname ohne Endung, Muster `^[A-Za-z0-9][A-Za-z0-9_-]*$`) |
| `POST /api/ai/diagnose` | `{step: StepResult-JSON, include_output: bool=false, send}` | dito, `kind: "text"` |
| `POST /api/ai/apply` | `{kind: "module"|"workflow", raw, target_name}` | `{path}`; validiert erneut, schreibt nur in den Nutzerordner, Module: Registry neu geladen. Fehler → 422 `validation` |

Laufzeit-`cwd` eines Laufs: Anfragewert oder `config_dir()/runs/<run_id>`; wird angelegt.

## WebSocket `/ws/runs/{id}?token=…`

Server → Client, je Nachricht ein JSON-Objekt `{type, ...}` in Reihenfolge, beim Verbinden zuerst der bisherige Verlauf:

| type | Felder |
|---|---|
| `step_started` | `step_id, command, safety` |
| `output` | `step_id, stream: "stdout"|"stderr", text` |
| `step_finished` | `step_id, exit_code, ok, duration, attempt` |
| `step_skipped` | `step_id, reason` |
| `message` | `step_id, text` |
| `ask_request` | `step_id, title, text, fields: [VariableSpec + name], current: {name: wert}, buttons, timeout (s oder null), error (str oder null)`; Lauf wartet auf `/answer` oder WS `answer`. Bei ungültigem Wert kommt dasselbe Ereignis erneut mit `error` und den getippten Werten in `current` (Geheimnisse nie) |
| `confirm_request` | `step_id, command, safety, reasons` (Lauf wartet, bis `/confirm` oder WS-Nachricht kommt) |
| `terminal_request` | `step_id, command` (vom Runner maskiert), `transcript: bool` (Ausgabe wird gespeichert, im UI anzeigen): Terminal-Schritt wartet auf `/ws/runs/{id}/terminal/{step_id}`; ohne Verbindung binnen 600 s → Exit 124 und `message` „Kein Terminal verbunden“ |
| `terminal_closed` | `step_id, exit_code, transcript: name|null` |
| `finished` | `status: "success"|"failed"|"aborted", message, exit_code` |

Client → Server: `{type: "confirm", step_id, ok}` und `{type: "answer", step_id, values, button}` bzw. `{type: "answer", step_id, cancel: true}` und `{type: "control", action}`; gleichwertig zu den REST-Aufrufen.

## Terminal `/ws/runs/{id}/terminal/{step_id}?token=…` (Phase 7, SECURITY.md 7)

Gleiche Token-, Host- und Origin-Prüfung wie alle `/ws/`-Pfade (4401/4403/4400, kein Prozess). Ablauf:

1. Nach `terminal_request` verbindet der Client; erste Nachricht Text `{"type":"open","cols":1–500,"rows":1–500}`. Andere erste Nachricht → Close 1008, Terminal bleibt für eine neue Verbindung frei.
2. Dann startet der Prozess (immer in bwrap, PTY). Server → Client: Binary-Frames mit Rohausgabe (≤ 64 KiB). Client → Server: Binary-Frames = Tastatureingaben, Text nur `{"type":"resize","cols","rows"}`; Sonstiges → `{"type":"error","message"}`, Verbindung bleibt.
3. Eingaben werden nie geloggt, publiziert oder gespeichert. Sie blockieren den Server nicht: was das Programm nicht sofort annimmt, wird gepuffert (max. 1 MiB, sonst 4413). Liest der Client die Ausgabe zu langsam (über 1 MiB ausstehend), pausiert der Server das Lesen vom Programm und setzt ab 512 KiB fort; die Verbindung bleibt.
4. Ablehnungen (4404, 4409, 4429) kommen nach `accept()` mit Begründung, damit der Browser den Code sieht. Trennen beendet den Prozess (SIGHUP, nach 2 s SIGKILL an die Gruppe), kein Reattach.

| Close-Code | Bedeutung | Exit-Code an den Lauf |
|---|---|---|
| 1000 `exit:<code>` | Programm beendet (Signal → 128+n) | `<code>` |
| 1000 `aborted` | Lauf abgebrochen | 130 |
| 1008 | erste Nachricht kein gültiges `open` | – (wartet weiter) |
| 1011 | Start fehlgeschlagen (z. B. kein bwrap), plus `message`-Event mit Installationshinweis | 126 |
| 1011 `Transkript nicht schreibbar` | Schreibfehler im Transkript, plus `message`-Event | 129 |
| 4404 | Lauf/Schritt unbekannt oder kein offener `terminal_request` | – |
| 4408 | 15 min ohne Ein-/Ausgabe oder `timeout` des Schritts erreicht | 124 |
| 4409 | Terminal hat schon eine Verbindung | – |
| 4413 | Programm nimmt keine Eingaben an: über 1 MiB Eingabe gepuffert | 129 |
| 4429 | schon 4 Terminals offen (`MAX_TERMINALS`) | – |
| (Client trennt) | | 129 |

Ohne bwrap startet der Schritt nicht: kein `terminal_request`, `message` mit Installationshinweis, Exit 126.
Transkript (nur mit `transcript: true` beim Anlegen): `cache_dir()/terminal/<run_id>-<step_id>[-n].txt`, Ordner 0700, Datei 0600 (`O_EXCL`), nur Programmausgabe inklusive Echo, Secret-Werte (Laufzeitwerte aus `TerminalRequest.secrets`) zeilenweise maskiert (best effort).

## Frontend-Kontrakt

- Kanonisches Modell ist das Workflow-Dokument (Schema `schemas/workflow.schema.json`). Der Graph wird daraus abgeleitet, nie umgekehrt gespeichert; nur `layout.nodes` wird aus der Ansicht zurückgeschrieben.
- TypeScript-Typen werden aus `schemas/*.json` generiert (`gui/src/types/`), nicht per Hand gepflegt.

## Einstellungen (Phase 6)

Datei `~/.config/whattheshell/settings.yaml` (Modus 0600, `schema_version: 1`), Modell `whattheshell.settings.Settings`. Sie enthält **nie Schlüssel**: `key_env` ist nur der Name einer Umgebungsvariable (Werte wie `sk-…` oder länger als 64 Zeichen werden abgelehnt), Felder mit `key` im Namen sind verboten.

| Feld | Standard |
|---|---|
| `ai.enabled` | `false` (F-27: aus = kein KI-Code-Pfad, kein Netzwerk, keine Fremdprozesse) |
| `ai.provider` | `local` (`local`, `api`, `agent`) |
| `ai.local` | `base_url: http://127.0.0.1:11434/v1`, `model: ""`, `timeout: 120` |
| `ai.api` | `kind: anthropic` (`anthropic`, `openai`), `base_url: null`, `model: ""`, `key_env: ANTHROPIC_API_KEY`, `key_source: env` (`env`, `keyring`), `timeout: 120` |
| `ai.agent` | `kind: claude` (`claude`, `codex`), `model: ""` (leer = Standardmodell), `reasoning: ""` (`low`/`medium`/`high`, nur Codex), `timeout: 300`; kein Feld `command` (ein altes `command` in der Datei erzeugt einen Ladefehler) |
| `ai.send_outputs` | `false` (Befehlsausgaben nur auf Wunsch mitsenden, F-30) |

Jeder KI-Einstieg ruft zuerst `ai.require_enabled(settings)` (wirft `AiDisabled`).

## KI-Endpunkte (`/api/ai/*`)

- Jeder Aufruf außer `GET /api/ai/check` und `GET /api/ai/agents` prüft zuerst `ai.enabled`: aus → 403 `{"error": "ai_disabled", message}`, noch vor der Body-Prüfung und bevor `ai.providers` importiert wird.
- Zweiphasig (F-30). `send: false` (Standard): `{"prompt": {"system", "user"}, "chars": n}`, nichts wird gesendet. `send: true`: `{"kind": "module"|"workflow"|"text", "raw", "errors": [str], "diff", "target": str|null, "valid": bool}`. Der Prompt ist in beiden Fällen um den Wert von `ai.api.key_env` maskiert. Nichts wird gespeichert oder ausgeführt; `raw` ist unvertraut und wird erst mit `apply` übernommen.
- `diagnose` ohne `include_output` entfernt `stdout`/`stderr` aus dem Schritt vor dem Prompt-Bau; `ai.send_outputs: true` erzwingt sie.
- `improve-module`/`examples`: Grundlage ist die Nutzerdatei (`target` = `<tool>.module.yaml`), sonst ein Gerüst aus dem rohen Katalog. Antwort mit anderem `tool:` → `valid: false`.
- Fehler: Anbieter nicht erreichbar oder fehlgeschlagen → 502 `ai_provider`; höchstens 2 Anbieteraufrufe gleichzeitig, Wartezeit über 15 s → 429 `busy`. Das Zeitlimit des Aufrufs selbst kommt aus `ai.<anbieter>.timeout`.
