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

## REST (JSON, UTF-8)

| Methode, Pfad | Anfrage | Antwort |
|---|---|---|
| `GET /api/status` | – | `{app, version, sandbox: SandboxStatus, module_errors: [{path, line, message}], config_dir, workflows_dir, modules_watch: bool, workflows_watch: bool}` (`modules_watch`/`workflows_watch`: Hot-Reload der Modul- bzw. Workflowdateien läuft). Die Hilfe-Abfrage unbekannter Tools läuft in der Sandbox, sobald der erste Selbsttest sie als verfügbar meldet |
| `POST /api/sandbox/selftest` | – | `SandboxStatus` (erneut geprüft) |
| `GET /api/tools?search=&lang=de|en` | – | `[{name, path, display_name?, category?, summary?, safety?}]` (Zusatzfelder nur aus geladenen Modulen, kein Hilfe-Abruf) |
| `GET /api/tools/{name}?sub=a/b&deep=0|1&refresh=0|1&lang=de|en` | – | `ToolInfo` (Modelle aus `schemas/`), `sub`-Wörter müssen `^[A-Za-z][A-Za-z0-9_-]*$` genügen (sonst 422), `name` dem Tool-Namensmuster. Unbekannte Subbefehle werden nicht abgefragt (kein Prozessstart): Fallback-Eintrag ohne Optionen. `lang` (Muster `^[a-z]{2,3}$`, Standard `de` = Originaltexte der Module): wendet `i18n[lang]` des Moduls auf `display_name`, `summary`, `description` sowie `label`/`help` von Optionen und Eingaben an (rekursiv); fehlt die Sprache oder ein Text, bleibt der Originaltext. Gleiches für `display_name`/`summary` in `GET /api/tools` |
| `GET /api/modules` | – | `{search_paths: [{dir, count, exists}], modules: [{priority, tool, path}], errors: [...]}` |
| `GET /api/modules/{tool}` | – | `{tool, source: "user"|"bundled", path, raw, document: Module|null, errors: [{path, line, message}], scaffold_available}`; Nutzerdatei (`config_dir()/modules/<tool>.module.yaml`) vor mitgelieferter; `document` ohne Standardwerte, `null` bei kaputter Datei (dann `errors`, `raw` bleibt); `scaffold_available` = Tool auf PATH. Kein Modul → 404 mit Hinweis auf `scaffold` |
| `PUT /api/modules/{tool}` | `{raw: str}` | Rohtext ist die Wahrheit: wird validiert (422 `validation` mit `errors: [{path, line, message}]`; `document.tool` ≠ `{tool}` → 422 `tool_mismatch`), atomar in die Nutzerdatei geschrieben, Registry neu geladen; Antwort `{tool, path}`. Mitgelieferte Module bleiben unberührt |
| `DELETE /api/modules/{tool}` | – | 204, löscht nur die Nutzerdatei (nur mitgeliefert → 403, sonst 404) und lädt die Registry neu |
| `POST /api/modules/scaffold` | `{tool, command: []}` | `{raw}`: Modul-Gerüst aus dem rohen Katalog (ohne Modul-Overrides, `Catalog` ohne Registry); 404 unbekanntes Tool, 422 bei ungültigen Wörtern |
| `GET /api/templates/{tool}` | – | `[{title, workflow: {id|null, document: Workflow|null}, error?}]`: `templates[]` aller Module des Tools, Pfad relativ zur Moduldatei (mitgelieferte Vorlagen liegen neben den Modulen), `id` = Dateiname ohne `.workflow.yaml`; unlesbare Vorlage → Eintrag mit `error` |
| `POST /api/command` | `{tool, command: [], args: {}, extra_args: []}` | `{argv: [], display, safety, reasons: []}` oder 422 mit `message` (ArgvError) |
| `POST /api/preview` | `{tool, command, args, extra_args, example: int|null, stdin: str|null}` | `{command, exit_code, stdout, stderr, duration, truncated, timed_out}`; Fixtures des gewählten Beispiels werden angelegt; 409 wenn Sandbox nicht verfügbar; nur in bwrap |
| `GET /api/workflows` | – | Workflow-Bibliothek: `[{id, name, description, source: "bundled"|"user"|"project", path, variables: {name: VariableSpec}, steps: int, error: str|null, shadows: [source], writable: bool}]` (`writable`: false, wenn eine Projektdatei gewinnt). Suchordner in aufsteigender Priorität: mitgeliefert, `config_dir()/workflows`, `<cwd der App>/.whattheshell/workflows`; Endungen `.workflow.yaml|.yml|.json`, `id` = Dateiname ohne Endung. Es erscheint nur der Gewinner, `shadows` nennt die überdeckten Quellen. Kaputte Dateien erscheinen mit `error` (`Pfad:Zeile: Meldung`), `name` = id. Der Index wird live nachgeladen |
| `GET /api/workflows/{id}` | – | `{id, path, document: Workflow, raw: str}` des Gewinners |
| `PUT /api/workflows/{id}` | `{document: Workflow}` | validiert (422 mit `errors: [{path, message}]`), gewinnt eine Projektdatei, 409 `shadowed`; sonst schreibt YAML in den Nutzerordner (andere Quellen bleiben unberührt; die Nutzerdatei gleicher id überschattet mitgelieferte), lädt den Index neu, antwortet `{id, path}` |
| `DELETE /api/workflows/{id}` | – | 204 (löscht nur die Nutzerdatei; liegt die id nur in `bundled` oder `project`, 403 mit Hinweis; gewinnt eine Projektdatei, 409 `shadowed`; Projektdateien von Hand entfernen; unbekannt 404) |
| `POST /api/workflows/{id}/run` | `{variables: {}, cwd: str|null, dry_run: bool}` | Abkürzung: lädt das Dokument des Gewinners aus dem Index und verhält sich wie `POST /api/runs` (gleiche Antwort und Fehler); unbekannte id 404 |
| `POST /api/workflows/validate` | `{document}` | `{ok, errors: [...]}` |
| `POST /api/runs` | `{document: Workflow, variables: {}, cwd: str|null, dry_run: bool}` | `{run_id, plan: str, needs_confirmation: bool, max_safety}`; bei `dry_run` kein Lauf, nur Plan. `prepare` läuft sofort (Tools auflösen, Klassen); Fehler → 422 |
| `GET /api/runs` | – | Gestartete Läufe, neueste zuerst, höchstens 50: `[{run_id, status, workflow_name, started, finished, exit_code}]` (ISO-8601, `finished`/`exit_code` null solange der Lauf läuft; nur im Speicher der App) |
| `POST /api/runs/{id}/start` | – | 202; startet den Lauf im Hintergrund (Workflow-Bestätigung nach 10.6 gilt mit diesem Aufruf als erteilt) |
| `GET /api/runs/{id}` | – | `{status, events: [...]}` (Verlauf, max 10 000 Events) |
| `POST /api/runs/{id}/control` | `{action: "abort"|"pause"|"resume"|"step"}` | 204 |
| `POST /api/runs/{id}/confirm` | `{step_id, ok: bool}` | 204 (Antwort auf `confirm_request`) |
| `GET /api/settings` | – | Settings-Dokument (siehe unten) plus schreibgeschütztes `key_status: "set"|"missing"` (ist die Umgebungsvariable `ai.api.key_env` gesetzt; der Wert wird nie ausgegeben) |
| `PUT /api/settings` | Settings-Dokument (ohne `key_status`) | Validierung wie `Settings` (unbekannte oder Schlüsselfelder → 422 `validation`, ohne Eingabewerte), schreibt atomar (0600), lädt die Einstellungen neu; Antwort wie `GET`. `ai.enabled` wird nur hier oder mit `wts ai enable` true |
| `GET /api/ai/check?network=1\|0` | – | `{ok, provider, items: [{name, ok, detail, hint}]}`: Preflight der konfigurierten Quelle (D-012). Ohne Gate: bei ausgeschalteter KI trotzdem 200 mit dem einzigen Item „KI aus“ (`ok: false`), damit die GUI es anzeigen kann; Anbieter-, Netz- und Prozesscode wird dann nicht geladen. `network=0` kontaktiert keinen Endpunkt; Agenten-CLIs werden immer gestartet (`--version`, Anmeldestatus im Temp-HOME). Fehler und Zeitlimits sind Items, nie 5xx |
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
| `confirm_request` | `step_id, command, safety, reasons` (Lauf wartet, bis `/confirm` oder WS-Nachricht kommt) |
| `finished` | `status: "success"|"failed"|"aborted", message, exit_code` |

Client → Server: `{type: "confirm", step_id, ok}` und `{type: "control", action}`; gleichwertig zu den REST-Aufrufen.

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
| `ai.agent` | `kind: claude` (`claude`, `codex`), `command: []` (leer = Standardaufruf), `timeout: 300` |
| `ai.send_outputs` | `false` (Befehlsausgaben nur auf Wunsch mitsenden, F-30) |

Jeder KI-Einstieg ruft zuerst `ai.require_enabled(settings)` (wirft `AiDisabled`).

## KI-Endpunkte (`/api/ai/*`)

- Jeder Aufruf außer `GET /api/ai/check` prüft zuerst `ai.enabled`: aus → 403 `{"error": "ai_disabled", message}`, noch vor der Body-Prüfung und bevor `ai.providers` importiert wird.
- Zweiphasig (F-30). `send: false` (Standard): `{"prompt": {"system", "user"}, "chars": n}`, nichts wird gesendet. `send: true`: `{"kind": "module"|"workflow"|"text", "raw", "errors": [str], "diff", "target": str|null, "valid": bool}`. Der Prompt ist in beiden Fällen um den Wert von `ai.api.key_env` maskiert. Nichts wird gespeichert oder ausgeführt; `raw` ist unvertraut und wird erst mit `apply` übernommen.
- `diagnose` ohne `include_output` entfernt `stdout`/`stderr` aus dem Schritt vor dem Prompt-Bau; `ai.send_outputs: true` erzwingt sie.
- `improve-module`/`examples`: Grundlage ist die Nutzerdatei (`target` = `<tool>.module.yaml`), sonst ein Gerüst aus dem rohen Katalog. Antwort mit anderem `tool:` → `valid: false`.
- Fehler: Anbieter nicht erreichbar oder fehlgeschlagen → 502 `ai_provider`; höchstens 2 Anbieteraufrufe gleichzeitig, Wartezeit über 15 s → 429 `busy`. Das Zeitlimit des Aufrufs selbst kommt aus `ai.<anbieter>.timeout`.
