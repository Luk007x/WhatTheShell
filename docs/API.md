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
| `GET /api/status` | – | `{app, version, sandbox: SandboxStatus, module_errors: [{path, line, message}], config_dir, workflows_dir, modules_watch: bool}` (`modules_watch`: Hot-Reload der Moduldateien läuft). Die Hilfe-Abfrage unbekannter Tools läuft in der Sandbox, sobald der erste Selbsttest sie als verfügbar meldet |
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
| `GET /api/workflows` | – | `[{id, name, path, source: "bundled"|"user"}]`, `id` = Dateiname ohne Endung, Nutzerordner `config_dir()/workflows` |
| `GET /api/workflows/{id}` | – | `{id, path, document: Workflow, raw: str}` |
| `PUT /api/workflows/{id}` | `{document: Workflow}` | validiert (422 mit `errors: [{path, message}]`), schreibt YAML in den Nutzerordner (eine mitgelieferte Datei bleibt unberührt; die Nutzerdatei gleicher id überschattet sie), antwortet `{id, path}` |
| `DELETE /api/workflows/{id}` | – | 204 (löscht nur die Nutzerdatei; ohne Nutzerdatei bei mitgelieferter id 403) |
| `POST /api/workflows/validate` | `{document}` | `{ok, errors: [...]}` |
| `POST /api/runs` | `{document: Workflow, variables: {}, cwd: str|null, dry_run: bool}` | `{run_id, plan: str, needs_confirmation: bool, max_safety}`; bei `dry_run` kein Lauf, nur Plan. `prepare` läuft sofort (Tools auflösen, Klassen); Fehler → 422 |
| `POST /api/runs/{id}/start` | – | 202; startet den Lauf im Hintergrund (Workflow-Bestätigung nach 10.6 gilt mit diesem Aufruf als erteilt) |
| `GET /api/runs/{id}` | – | `{status, events: [...]}` (Verlauf, max 10 000 Events) |
| `POST /api/runs/{id}/control` | `{action: "abort"|"pause"|"resume"|"step"}` | 204 |
| `POST /api/runs/{id}/confirm` | `{step_id, ok: bool}` | 204 (Antwort auf `confirm_request`) |

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
