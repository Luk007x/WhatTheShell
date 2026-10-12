# Sicherheitskonzept

Stand: Phase 4 (D-008, D-009). Maßgeblich ist `PROJEKTAUFTRAG.md` Abschnitt 10 und 11. Dieses Dokument beschreibt, was im Code **umgesetzt** ist (mit Datei und Funktion), und kennzeichnet alles andere als „geplant (Phase N)“ oder „nicht umgesetzt“.

## 1. Bedrohungsmodell

WhatTheShell startet beliebige Befehle des Nutzers; ein Fehler hat damit sofort Folgen für das System. Gefahren sind (1) Shell-Injektion aus Dateien, Variablen und GUI-Feldern, (2) versehentlich zerstörerische Befehle, (3) fremde Workflow- und Moduldateien (untrusted, auch als YAML-Bombe), (4) der Hilfe-Abruf unbekannter Tools (`--help` startet ein fremdes Programm) und (5) später die lokale Web-API, die Befehle ausführen kann und von anderen Webseiten im Browser erreichbar wäre. Nicht Teil des Modells: ein bereits kompromittiertes Nutzerkonto und Schäden, die der Nutzer nach Bestätigung bewusst auslöst.

## 2. Die acht Regeln aus Abschnitt 10

### 2.1 Kein `shell=True`, keine String-Konkatenation

| | |
|---|---|
| Gilt | Befehle sind immer eine argv-Liste. Der Befehlstext dient nur der Anzeige. |
| Umsetzung | `subproc.run_limited` ruft `subprocess.Popen(list(argv))` ohne Shell. `engine/argv.py:build_argv` baut die Liste aus Spec und Werten (Reihenfolge, `multiple`, `nargs`, `attached`); `display` quotet nur zur Anzeige (`shlex.join`). Unbekannte Feld-ids, falsche Typen und Enum-Werte werden mit `ArgvError` abgelehnt (`_convert`). |
| Test | `tests/unit/test_injection.py` (Nutzlasten mit `;`, `$()`, Backticks, Quotes, Newline, Unicode in `args`, `extra_args`, Variablen, `stdin.text`, `env`; prüft, dass keine Datei entsteht), `test_engine_argv.py`. |
| Grenzen | Ein Wert mit führendem `-` kann vom Zieltool als Option gelesen werden. Die Engine fügt kein `--` ein, weil nicht jedes Tool es kennt (FORMATS §7). Eine GUI-Warnung ist **nicht umgesetzt**. Ein aufgerufenes Programm, das selbst eine Shell startet (`sh -c`, `xargs`), wird dadurch nicht entschärft; solche Tools sind `caution`. |

### 2.2 Sicherheitsklassen

| | |
|---|---|
| Gilt | Jeder Befehl ist `safe`, `caution` oder `dangerous`; die höchste zutreffende Regel gewinnt. Module dürfen höher einstufen. |
| Umsetzung | `safety/classify.py:classify_command`: Tool-Listen `DANGEROUS_TOOLS` (rm, dd, mkfs.*, sudo, kill …) und `CAUTION_TOOLS`, Flag-Regeln `_FLAG_RULES` (`rm -r`, `chmod -R`, `find -delete/-exec`, `sed -i`, `--delete` …), `systemctl poweroff/reboot`, Kürzen bei `=` (`--output=x` trifft die Regel für `--output`), `sed -i<Suffix>` (`-i.bak`), alle `find`-Aktionen (`-delete`, `-exec`, `-ok`, `-okdir`, `-fprint*`, `-fls`), erweiterte `CAUTION_TOOLS` (Wrapper und Interpreter wie `timeout`, `busybox`, `awk`, `nc`, `socat`), Modul-Override über `OptionSpec.safety` und `CommandSpec.safety` als Basis. `summarize` bildet das Maximum über einen Workflow. |
| Test | `tests/unit/test_safety.py`. |
| Grenzen | Reine Heuristik auf Namen und Flags: Ein Tool unter anderem Namen (Symlink, Skript) oder Gefahr aus Werten (`dd of=/dev/sda`, Zielpfad) wird nicht erkannt. Gebündelte Kurzflags (`-rf`) werden nicht zerlegt (Ausnahme `sed -i…`), sonst treffen nur exakte Flags (vor `=`). Die Tool-Listen wirken immer: `raise_to` hebt nur an, ein Modul kann die Klasse eines Tools aus den Listen nicht absenken. Unbekannte Tools bleiben bei der Basisklasse (`safe`). |

### 2.3 Vorschau nur in der bwrap-Sandbox

| | |
|---|---|
| Gilt | Kein ungeschützter Ersatzmodus. Nur ein beschreibbares Arbeitsverzeichnis, kein Netz, bereinigte Umgebung, Zeit-, Speicher- und Ausgabelimit. |
| Umsetzung | `sandbox/__init__.py:build_bwrap_argv`: `--ro-bind / /`, `--tmpfs` für `/tmp`, `/var/tmp`, `/home`, `/root`, `/run`, Workdir als einzige Schreibstelle unter `/tmp/work`, `--unshare-all` (inkl. Netz und PID), `--die-with-parent`, `--new-session`, `--clearenv`. `run_sandboxed` liefert `None`, wenn `bwrap` fehlt, und startet nie ohne bwrap; Limits: Timeout 10 s und 1 MiB Ausgabe über `run_limited`; Speicher und Prozesse über `prlimit --as=512 MiB --nproc=256` **innerhalb** von bwrap (kein `preexec_fn`, wegen Fork-Risiko in Mehrthread-Prozessen). Fester `PATH` (`SANDBOX_PATH`), nicht überschreibbar. `self_test` prüft Start, Schreiben im Workdir, Netzisolation (`ip link`, nur wenn `/usr/sbin/ip` existiert) und Schreibschutz (`/etc`); bei Fehler `SandboxStatus(available=False, reason, install_hint)`, Installationsbefehl je Distribution aus `/etc/os-release` (`install_hint_for_distro`). Eingesetzt wird die Sandbox für Modul-Beispiele (`sandbox/examples.py:run_example`, bei `available=False` übersprungen). |
| Test | `tests/unit/test_sandbox.py` (Aufbau der Argumente, Schreibschutz, Workdir, Umgebung, kein Netz, Timeout, Selbsttest, Installationshinweise), `test_examples_sandbox.py`. |
| Grenzen | (a) bwrap braucht unprivilegierte User-Namespaces; wo sie gesperrt sind (AppArmor, Sysctl), ist die Vorschau aus. (b) Das Dateisystem ist **lesbar** (`--ro-bind / /`): `~/.ssh` ist zwar durch `--tmpfs /home` verdeckt, andere Pfade (`/etc`, `/usr`, Daten außerhalb von `/home`) sind lesbar. (c) Das Arbeitsverzeichnis liegt unter `/tmp/work`, weil auf dem schreibgeschützten Root kein `/work` angelegt werden kann. (d) `--as` begrenzt Adressraum, nicht tatsächlichen Speicher; `nproc` zählt je Benutzer im User-Namespace (256), keine CPU-Grenze. Fehlt `prlimit` (util-linux), läuft die Sandbox mit Warnung **ohne** Speicher- und Prozesslimit; der Selbsttest meldet das. (e) Die Netzisolation im Selbsttest wird übersprungen, wenn `ip` fehlt. (f) Die Web-UI bietet `POST /api/preview` (nur Sandbox, 409 ohne bwrap) und `POST /api/sandbox/selftest` („Erneut testen“); ob eine automatische Vorschau nur für `safe` gesperrt wird, habe ich im Frontend nicht geprüft. Einen CLI-Befehl für eine Vorschau beliebiger Befehle gibt es nicht. Der Schalter „Geschützter Lauf“ für ganze Workflows ist **geplant (Phase 3, optional)**: **nicht umgesetzt**. |

### 2.4 Bestätigung vor echter Ausführung

| | |
|---|---|
| Gilt | `caution` und `dangerous` verlangen eine Bestätigung mit Klartext-Befehl. Dry-Run ist immer verfügbar. |
| Umsetzung | `safety/classify.py:needs_confirmation`; `engine/runner.py:Runner._command` ruft vor dem Start `confirm(ConfirmRequest(step_id, Befehlstext, Klasse, Gründe))`. Bei Ablehnung endet der Lauf mit Status `aborted`, ohne Prozessstart. Die Klasse wird **zweimal** bestimmt, es gilt das Maximum (`merge_verdicts`, D-008): in `Runner.prepare` für Plan und Übersicht, und in `Runner._build` zur Laufzeit auf den gerenderten Werten (Variablen, Schleifenwerte, Tool-Ausgaben könnten sonst `--delete` nachschieben). Zusätzlich heben `env`, ein `cwd` oder `stdin.file` außerhalb des Workflow-Ordners auf `caution` (`extra_risks`); der Bestätigungstext zeigt Umgebung, Verzeichnis und stdin (`describe`). `Runner.prepare` startet keinen Prozess für die Klassifizierung. CLI: `cli.py` zeigt vor jedem Lauf die Übersicht (`engine/plan.py`), `--dry-run` führt nichts aus (siehe 2.9: Hilfe-Abruf nur für bekannte Subbefehle), ohne Terminal ohne `--yes` Abbruch (Exit 2). |
| Test | `tests/unit/test_engine_runner.py` (`test_confirmation_refused_starts_no_process`), `test_engine_plan.py`, `test_cli_run.py`. |
| Grenzen | `--yes` bestätigt alles ohne Rückfrage (bewusst, für Skripte). Die Bestätigung gilt je Schritt (und je Schleifeniteration, eine „für alle“-Antwort ist weiterhin offen); variablenabhängige Befehle werden mit den eingesetzten Werten angezeigt. In der Web-UI läuft die Bestätigung als `confirm_request` über WebSocket/REST (Abschnitt 4). |

### 2.5 Kein stilles Sudo

| | |
|---|---|
| Gilt | Rechteerhöhung nur sichtbar und bestätigt. |
| Umsetzung | `sudo`, `su`, `doas`, `pkexec`, `chroot` stehen in `DANGEROUS_TOOLS` und lösen immer die Bestätigung aus. Es gibt keinen Code, der von sich aus `sudo` voranstellt. |
| Test | `test_safety.py` deckt die Klassifizierung nur indirekt ab (kein eigener Test für `sudo`). |
| Grenzen | Das gilt nur, solange `sudo` als Tool erkannt wird. Ein Tool, das intern `sudo` aufruft (z. B. über `env`-Wrapper, Skript, `pkexec`-Helfer), ist nicht erkennbar. `sudo` benötigt ein Terminal für das Passwort; die Engine reicht kein Passwort durch (stdin ist `/dev/null`, außer bei `stdin`-Schritten). |

### 2.6 Workflow-Dateien sind untrusted

| | |
|---|---|
| Gilt | Beim Öffnen wird nichts ausgeführt; vor dem ersten Lauf sieht der Nutzer alle Befehle mit Gefahrenklasse. |
| Umsetzung | `modules/loader.py:load_workflow_file` liest und validiert nur. `Runner.prepare` führt nichts aus (löst Tools auf, klassifiziert). CLI zeigt `plan_text(plan(prepared))` vor jedem echten Lauf (siehe 2.4). Beim Auflösen eines Tools kann der Hilfe-Abruf `--help` des Tools starten (siehe 2.9). |
| Test | `test_engine_plan.py`, `test_cli_run.py`, `test_modules_loader.py`. |
| Grenzen | Die Zusammenfassung erscheint im CLI automatisch, aber nur bei `caution`/`dangerous` wird zusätzlich ausdrücklich gefragt. Eine Herkunftsmarkierung („fremde Datei, noch nie bestätigt“) gibt es nicht: **nicht umgesetzt**. In der Web-UI liefert `POST /api/runs` den Plan vor `/start` (Abschnitt 4). |

### 2.7 Template-Ausdrücke ohne Codeausführung

| | |
|---|---|
| Gilt | `{{ … }}` kennt nur Referenzen, keine Ausdrücke, Aufrufe oder Filter. |
| Umsetzung | `engine/template.py`: ein einziger regulärer Ausdruck `_REF` erlaubt `name` oder `name.feld`; alles andere wird als `TemplateError` abgelehnt. Reguläre Ausdrücke aus Dateien (Bedingungen) laufen nur auf Texten bis zum Ausgabelimit (1 MiB); katastrophales Backtracking ist damit begrenzt, nicht ausgeschlossen (D-008). Gerenderte Werte werden nur als Text in argv-Elemente, `stdin` oder `env` eingesetzt, nie geparst oder ausgewertet. Bedingungen und Schleifen laufen über `engine/evaluate.py`. |
| Test | `test_engine_template.py`, `test_engine_evaluate.py`, `test_injection.py`. |
| Grenzen | `engine/evaluate.py` wurde für dieses Dokument nicht im Einzelnen geprüft; die Aussage „keine Codeausführung“ stützt sich auf `template.py` und die Tests. |

### 2.8 Logs ohne Geheimnisse

| | |
|---|---|
| Gilt | Werte von Variablen mit `type: secret` erscheinen nie im Klartext in Anzeige, Ereignissen und Ergebnis. |
| Umsetzung | `engine/runner.py:secret_values`, `mask_text` (ersetzt durch `***`). Die Maskierung geschieht **zentral in `Runner._emit`**: jedes Textfeld jedes Ereignisses (`StepStarted.command`, `OutputChunk`, `Message`, `StepSkipped`, `WorkflowFinished`) wird dort maskiert, einzelne Aufrufstellen können sie nicht vergessen. Zusätzlich maskiert: der angezeigte Befehl samt argv, `env`, `cwd` und stdin-Label (`_build`/`describe`), Ergebnisse (`_record`) und Ergebnis-Variablen. `_LineEmitter` setzt Zeilen vor dem Emit zusammen, damit ein über zwei Reads geteiltes Secret nicht durchrutscht. Fehlermeldungen nennen den Feldnamen, nicht den Wert (wertfreie Meldungen, damit keine `repr`-Form des Werts entsteht). `default` bei Secrets ist im Schema verboten (D-005). |
| Test | `test_engine_runner.py:test_secret_masked_everywhere`. |
| Grenzen | Maskiert wird der exakte Wert. Abgeleitete Formen (Base64, URL-kodiert, gekürzt) bleiben sichtbar. Ein Secret **mit Zeilenumbruch**, das über Chunk-Grenzen verteilt ausgegeben wird, kann an der Zeilenzusammensetzung vorbeikommen. Das Secret steht zwangsläufig in argv und damit in `/proc/<pid>/cmdline` für andere Prozesse desselben Nutzers; besser über `env` oder `stdin` übergeben. Der Roh-Text für Pipes und Templates bleibt im Speicher unmaskiert (`_record`). Einzelne Meldungen außerhalb von `_emit` (z. B. `RunError` aus `prepare` bei falschem Variablentyp, Template-Fehler mit Textauszug) können noch den Wert enthalten; das wurde nicht lückenlos geprüft. Ein Schlüsselbund für Secrets ist **nicht umgesetzt**. |

## 2a. Weitere umgesetzte Schutzmaßnahmen

| Maßnahme | Ort | Test |
|---|---|---|
| Prozessgruppe pro Lauf (`start_new_session`), stdin wird aus einem eigenen Thread geschrieben (kein Blockieren bei großen Eingaben), kein `preexec_fn`; Kill der ganzen Gruppe bei Timeout, Ausgabelimit und Abbruch | `subproc.py:run_limited`, `_kill_group` | `test_subproc.py` (`test_timeout_kills_grandchild`, `test_byte_limit`, `test_cancel_kills_process_group`) |
| Umgebungs-Sperrliste für `env` in Schritten, **zweite Linie**: Präfixe `LD_*`, `GIT_CONFIG*`, Namen wie `PATH`, `PYTHONPATH`, `BASH_ENV`, `ENV`, `IFS`, `PROMPT_COMMAND`, `NODE_OPTIONS`, `PERL5OPT`, `RUBYOPT`, `GIT_SSH_COMMAND`, `PAGER`, `EDITOR` u. a. sowie ungültige Namen werden mit Warnung verworfen. Erste Linie: jedes gesetzte `env` hebt den Schritt auf `caution`. Eine Allowlist würde echte Workflows brechen (D-008) | `engine/runner.py:_BLOCKED_ENV`, `env_blocked`, `Runner._build` | `test_engine_runner.py:test_env_blocklist` |
| Ausgabelimit und Timeout je Schritt | `Runner._execute` (`output_limit`, `step.timeout`, Obergrenze 24 h) | nicht gesondert geprüft; `run_limited` ist in `test_subproc.py` getestet |
| Hilfe-Abruf: Denylist und Limits | `catalog/fetch.py` (siehe 2.9) | `test_catalog_fetch.py` |

Grenzen dieser Gruppe:

- Ein daemonisierter Enkelprozess, der seine Pipes schließt und die Sitzung wechselt, entkommt dem Gruppen-Kill (`# ponytail`-Kommentar in `run_limited`).
- Reale Läufe auf dem Host erben die **volle Umgebung des Nutzers** (`dict(os.environ)` in `_build`), nicht die bereinigte. Das ist gewollt (Workflows brauchen `HOME`, `PATH`), heißt aber: Secrets in Umgebungsvariablen sind für jedes gestartete Tool sichtbar.
- Das Sperren von `PATH` verhindert nicht, dass ein Befehl wie `env` Umgebungswerte setzt; `env` ist deshalb `caution`.
- Speicher- und Prozesslimit (`prlimit`) gelten nur in der Sandbox, nicht bei Läufen auf dem Host.

### 2.9 Hilfe-Abruf unbekannter Tools (Katalog)

Der Katalog startet zum Lesen der Hilfe fremde Programme (`catalog/fetch.py:fetch_help`). Das ist kein Punkt aus Abschnitt 10, aber Teil des Bedrohungsmodells.

- **Nur bekannte Subbefehle:** `Catalog.get(tool, command)` fragt `tool sub --help` nur ab, wenn `sub` im Elternbefehl (Katalog oder Modul) bekannt ist; sonst Fallback-Eintrag (`source="fallback"`) ohne Prozessstart (`catalog/catalog.py`, Parameter `probe_unknown`, Standard `False`). Grund: Eine fremde Workflow-Datei konnte sonst beim `--dry-run` über `sh -c` Code starten (D-008). Nur `wts inspect` setzt `probe_unknown`, weil der Nutzer den Subbefehl selbst eintippt. Zusätzlich erlaubt `models/workflow.py` für `command`-Wörter nur das Muster `^[A-Za-z][A-Za-z0-9_-]*$` (keine Optionen, kein Pfad).
- **Annahme:** `--help` und `-h` sind harmlos (D-006). Das ist keine Garantie. Ausnahmen werden über die Denylist `NEVER_PROBE` (shutdown, reboot, halt, poweroff, init, telinit, kexec) abgefangen, geprüft gegen Basisname **und** aufgelösten Symlink. Weitere gefährliche Tools sind **nicht** erfasst; die Liste ist bewusst klein.
- Der Abruf läuft über `run_limited`: eigene Prozessgruppe, Timeout 5 s, 1 MB Ausgabe, `sanitized_env()` (`LC_ALL=C`, `TERM=dumb`, nur `PATH` und `HOME` übernommen), stdin geschlossen. **Nicht** in der Sandbox: Das Tool läuft mit den Rechten des Nutzers und mit Netzzugang.
- Test: `tests/unit/test_catalog_fetch.py`, `test_subproc.py`.

## 3. Vertrauensgrenzen für Dateien

Modul- und Workflow-Dateien (Suchpfade nach FORMATS §6: gebündelt, `~/.config/whattheshell/`, `./.whattheshell/`) sowie der Katalog-Cache sind **fremder Input**.

| Quelle | Schutz | Ort | Grund |
|---|---|---|---|
| Modul-/Workflow-Datei | maximal 1 MiB (`MAX_DOCUMENT_BYTES`), Prüfung **vor** dem Lesen über `stat` | `modules/loader.py:_load` | Speicherverbrauch, Parser-Laufzeit |
| YAML-Aliase/-Anker | abgelehnt: ein Container, der zweimal erreichbar ist, löst `ValueError` aus | `loader.py:_plain` | „Billion laughs“; Test hält 1 s ein |
| Verschachtelungstiefe | **kein fester Grenzwert**; `RecursionError` und `MemoryError` werden als `DocumentError` gemeldet | `loader.py:load_document` | Schutz vor Absturz; eine tiefe Datei deaktiviert nur sich selbst (Test mit 100000 Klammern) |
| Schema | Pydantic-Validierung, Fehler mit Datei, Zeile und Feldpfad | `loader.py:_load` | Falsche Struktur wird nie halb übernommen |
| Fehlerisolation | eine fehlerhafte Datei deaktiviert nur sich selbst | `modules/registry.py` (`registry.errors`) | F-23 |
| Katalog-Cache | `~/.cache/whattheshell/` (`$XDG_CACHE_HOME`); beim Lesen werden JSON und Modell validiert, bei Fehler wird der Eintrag verworfen und neu erzeugt; Schlüssel `path + mtime_ns + size` | `catalog/catalog.py` (`_read`, `_write`) | Beschädigter oder manipulierter Cache führt nicht zu einem Absturz |

Test: `tests/unit/test_modules_loader.py` (`test_alias_bomb`, `test_deep_nesting_and_scan`, `test_too_big`), `test_modules_registry.py`, `test_catalog.py`.

Grenzen:

- Ein Modul darf Optionen höher einstufen, **nicht** die Tool-Listen in `classify.py` aufweichen. Ein bösartiges Modul kann aber irreführende Beschreibungen, Beispiele oder falsche Flags liefern (der Befehl, der angezeigt wird, ist dennoch der, der läuft).
- Der Cache ist nicht signiert; wer in `~/.cache` schreiben kann, kann Hilfe-Texte und Optionen fälschen. Der Schutz davor ist das Dateisystem-Recht des Nutzers.
- Module aus `./.whattheshell/modules/` (projektlokal) werden beim Scan automatisch geladen. Eine Rückfrage vor dem Laden fremder Projektmodule gibt es nicht: **nicht umgesetzt**.
- Module werden beim Laden nie ausgeführt; Beispiele laufen nur in der Sandbox (2.3).

## 4. Web-UI (umgesetzt, Phase 4)

`wts gui` startet den lokalen Server (`cli.py:_gui`, `_serve`); Vertrag in `docs/API.md`, Entscheidung D-009. Tests: `tests/unit/test_api_security.py`, `test_api_rest.py`, `test_api_runs.py`. Jeder Punkt der Checkliste aus Abschnitt 11 ist umgesetzt:

- [x] **Nur `127.0.0.1`, selbst gebundener Socket.** `cli.py:_gui` bindet `socket.bind(("127.0.0.1", port))` selbst und übergibt den Socket an uvicorn (`_serve`, `serve(sockets=[sock])`): kein Port-Race, kein Browserstart auf einen fremden Dienst. Kein `0.0.0.0`, kein IPv6.
- [x] **Kein Start als root.** `cli.py:_gui` bricht bei `os.geteuid() == 0` mit Meldung ab.
- [x] **Sitzungstoken.** `api/security.py:Session` erzeugt `secrets.token_urlsafe(32)` pro Start. `wts gui` gibt `http://127.0.0.1:PORT/#token=…` aus; das Fragment geht nie an den Server. Die SPA sendet den Header `X-WTS-Token`; beim WebSocket Query `?token=`. Prüfung in `SecurityMiddleware._violation` mit `secrets.compare_digest` für alles unter `/api/` und `/ws/` (401). Kein Access-Log (`access_log=False` in `_serve`), damit die WebSocket-Query nicht im Log landet.
- [x] **Host-Prüfung** gegen DNS-Rebinding: `_violation` erlaubt nur `127.0.0.1:PORT` und `localhost:PORT` (400), für alle Pfade inklusive statischer Dateien.
- [x] **Origin-Prüfung** gegen CSRF und Cross-Site-WebSocket: `_violation` prüft `Origin` bei allen Nicht-GET/HEAD/OPTIONS-Anfragen und bei WebSocket (403). Ein fehlender Origin (z. B. `curl`) wird zugelassen; dort schützt das Token.
- [x] **Keine CORS-Header.** Es gibt keine CORS-Middleware (`api/app.py:create_app`); die Seite wird von derselben Origin ausgeliefert.
- [x] **Keine Doku-Endpunkte.** `create_app`: `docs_url=None, redoc_url=None, openapi_url=None`.
- [x] **Body-Limit** 1 MiB: `MAX_BODY_BYTES`, per `Content-Length` und für Körper ohne Länge im Zähler `SecurityMiddleware._limited` (413). WebSocket-Nachrichten: `ws_max_size=1_048_576` in `_serve`.
- [x] **Vorschau-Semaphore.** `api/rest.py:PREVIEW_SLOTS = Semaphore(2)`; Wartezeit über 15 s gibt 429. Die Vorschau läuft nur über `run_sandboxed`, ohne Sandbox 409.
- [x] **Laufgrenzen.** `api/runs.py`: `MAX_RUNNING_RUNS = 4` (429), `MAX_CREATED_RUNS = 20`, `MAX_FINISHED_RUNS = 50` (älteste werden verworfen), `MAX_EVENTS = 10_000` je Verlauf. `cwd` muss ein existierender absoluter Ordner sein (422), sonst `config_dir()/runs/<id>`.
- [x] **Subbefehle werden nie abgefragt.** Die API ruft `Catalog.get` ohne `probe_unknown` (Standard `False`); Subbefehl-Wörter und `command` müssen `^[A-Za-z][A-Za-z0-9_-]*$` genügen (`rest.py:SubWord`, 422). Unbekannte Subbefehle liefern einen Fallback-Eintrag ohne Prozessstart (siehe 2.9, D-009).
- [x] **Browserstart ohne Token in der Prozessliste.** `cli.py:_write_redirect` schreibt eine Weiterleitungsseite (`O_EXCL`, Modus 0600, Ordner 0700 unter `cache_dir()/gui`); `webbrowser.open` bekommt nur die `file://`-URL. Die Datei wird beim Beenden gelöscht (`finally` in `_gui`).
- [x] **Einheitliches Fehlerformat.** `api/errors.py:error_response` und die Handler in `app.py` (`_http_error`, `_validation_error`) liefern `{"error", "message"[, "errors"]}`; keine Stacktraces in Antworten (Stacktraces gehen nur ins Log).
- [x] **Gleiche Logik wie das CLI.** Ausführung läuft über `Runner` (Klassifizierung, Bestätigung als `confirm_request`, Maskierung in `_emit`), Befehle über `build_argv`; die API umgeht `needs_confirmation` nicht.

Bekannte Grenzen:

- Jeder Client mit gültigem Token, also auch ein zweiter Tab desselben Nutzers, kann Bestätigungen beantworten. Es ist derselbe Nutzer; eine Bindung an eine Verbindung gibt es nicht.
- Die erste URL mit `#token=…` steht im Browserverlauf und in der Terminalausgabe. Das Token gilt nur für diese Sitzung.
- Wird `wts gui` mit SIGKILL beendet, bleibt die Weiterleitungsdatei mit dem Token liegen (0600, nur für den Nutzer lesbar, Token wertlos nach Ende des Servers).
- XSS-Fläche der SPA: im Frontend gibt es kein `dangerouslySetInnerHTML` und kein `innerHTML` (per `grep` in `gui/src` geprüft); Tool-Ausgaben werden als Text gerendert. Ein XSS-Fehler hätte wegen des Tokens im Speicher der Seite die Rechte der API. Eine Content-Security-Policy ist **nicht umgesetzt**.
- Fehlermeldungen können Texte des Betriebssystems und Pfade enthalten (z. B. `Workflow nicht schreibbar: …`, `Interner Fehler: …` bei einem abgestürzten Lauf in `runs.py:_run`), nur lokal sichtbar.
- Hilfe-Abruf läuft in der bwrap-Sandbox, sobald sie verfügbar ist (`catalog/fetch.py`); Tools unter `/home`, `/root`, `/tmp`, `/var/tmp`, `/run` (dort in der Sandbox verborgen) und Fälle ohne brauchbaren Sandbox-Text laufen zusätzlich auf dem Host (Denylist gilt, 2.9), `source=fallback` wird nie gecacht.
- Ein Prozess desselben Nutzers kann den Port erreichen und die Token-Datei lesen; Schutz vor lokalen Angreifern mit Nutzerrechten gehört nicht zum Modell.

## 5. KI-Funktionen (umgesetzt, Phase 6)

Entscheidung D-011; Anforderungen F-27 bis F-31 (Projektauftrag 6.6, Kurzfassung F-30). Tests: `test_ai_gate.py`, `test_ai_providers.py`, `test_ai_tasks.py`, `test_api_ai.py`, `test_cli_ai.py`, `test_settings.py`, `test_api_settings.py`.

| Regel | Umsetzung | Nachweis |
|---|---|---|
| Standard aus, Gate ohne Provider-Import (F-27) | `settings.py`: `ai.enabled` ist standardmäßig aus. `ai/__init__.py` importiert weder Provider noch `urllib`, `socket` oder `subprocess`; `require_enabled` ist der erste Schritt jedes Einstiegs (`cli.py` bei jeder Aufgabe, `api/ai_api.py:_gate` als Abhängigkeit aller Aufgaben-Endpunkte, 403; `GET /api/ai/check` meldet stattdessen „KI aus“ über `ai/check.py:check`, das Provider erst nach derselben Prüfung importiert), `ai/protocol.py:make_provider` importiert `ai.providers` erst danach. | `test_ai_gate.py`: `socket.socket`, `socket.create_connection` und `subprocess.Popen` werden auf Fehler gepatcht; bei ausgeschaltetem Schalter bleibt `whattheshell.ai.providers` aus `sys.modules`. Auch die Einstellungsbefehle brauchen weder Netz noch Prozess noch Provider. |
| Schlüssel nie in Dateien | `settings.py:ApiSettings`: Feldnamen mit „key“ außer `key_env`/`key_source` werden abgelehnt; `key_env` muss ein Variablenname sein. `ai/providers/keys.py:resolve_key` liest nur Umgebung oder Schlüsselbund (optionales Extra `keyring`, lazy import); Fehlermeldungen nennen den Namen, nie den Wert. Maskierung in Vorschau-Folgen, Fehlern und Antworten: `ai/tasks.py:known_keys` und `sanitize` (Secrets maskieren, Steuerzeichen entfernen), genutzt in `cli.py` und `api/ai_api.py`. | `test_settings.py`, `test_ai_providers.py` (`test_resolve_key_env`, `test_resolve_key_keyring`), `test_ai_tasks.py:test_sanitize_and_known_keys` |
| Datenvorschau vor dem Senden | `cli.py:_preview_text` zeigt System- und Nutzertext **vollständig** mit Längen; gesendet wird erst nach Bestätigung (`--yes`, sonst Rückfrage; ohne Terminal und ohne `--yes` Abbruch); `--preview-file` schreibt die Vorschau nach 0600. Web: zweiphasig (Vorschau, dann Senden) in `api/ai_api.py`. | `test_cli_ai.py`, `test_api_ai.py` |
| Befehlsausgaben nur auf Wunsch | `ai/tasks.py:diagnose`: ohne `include_output` gehen nur Befehl, Exit-Code, Dauer und Status, keine Ausgabezeile; mit Wunsch gekürzt (`_clip`). Auslöser: `--include-output`, `include_output` in der API oder die Einstellung `ai.send_outputs`. | `test_ai_tasks.py`, `test_api_ai.py` |
| Ergebnisse nur als Dateien, nichts wird ausgeführt | `ai/tasks.py:extract_yaml` zieht das YAML aus der Antwort; `modules/store.py:validate_module_text` und `validate_workflow_text` prüfen mit dem normalen Lader (`load_document`, Limits aus Abschnitt 3). Die Antwort wird nie ausgeführt; `diagnose` liefert reinen Text. | `test_ai_tasks.py`, `test_modules_loader.py` |
| Diff und getrennte Freigabe | `ai/approve.py:propose` erzeugt den Diff; `lowered_safety` setzt eine Warnung „ACHTUNG: Sicherheitsklasse … gesenkt“ vor den Diff, wenn ein Modul Befehl oder Option niedriger einstuft. CLI: `--yes` erlaubt das **Senden**, `--apply` das **Schreiben**; ohne `--apply` steht „Nichts gespeichert“. Web: `POST /api/ai/apply` validiert erneut. | `test_ai_tasks.py:test_lowered_safety_warning`, `test_cli_ai.py`, `test_api_ai.py` |
| Schreiben nur in den Nutzerordner | `ai/approve.py:apply` lehnt Vorschläge mit Validierungsfehlern, Art `text` und fehlendem Ziel ab; `target_path` verlangt ein Ziel direkt im Nutzerordner (kein Unterordner, kein fremdes Verzeichnis); `modules/store.py:user_path` erlaubt nur einfache Dateinamen mit passender Endung; `write_user_file` schreibt atomar mit 0600 (`atomic_write` ersetzt einen Symlink am Ziel, folgt ihm nicht). | `test_ai_tasks.py:test_apply_writes_only_allowed`, `test_apply_refuses_errors_text_and_symlink` |
| HTTP-Anbieter (lokal, API) | Nur Stdlib (`urllib.request`, `ai/providers/http.py:post_json`): keine Weiterleitung (`_NoRedirect`, ein 3xx wird zum Fehler), TLS-Standard, Proxy aus der Umgebung, Timeout. Fehlertexte des Servers: höchstens 200 Zeichen, Steuerzeichen ersetzt (`printable`). | `test_ai_providers.py:test_http_errors_and_redirect_refused` |
| Agenten-CLIs (F-28, D-012) | `ai/providers/agent_cli.py:AgentCliProvider` über `isolated_env`: Temp-Verzeichnis (0700) mit `home/` und `work/`; `HOME=home`, `XDG_CONFIG_HOME=home/.config`, `XDG_CACHE_HOME=home/.cache`, `cwd=work`. Hineinkopiert wird nur die Anmeldedatei (`~/.claude/.credentials.json` bzw. `~/.codex/auth.json`, 0600, nur wenn vorhanden); globales `CLAUDE.md`, `settings.json`, Hooks, Plugins, Skills und `config.toml` des Nutzers fehlen dort. Das Temp-Verzeichnis samt Sitzungsdateien wird nach jedem Aufruf gelöscht, auch bei Zeitlimit und Fehler. argv-Liste, Prompt über stdin, Umgebung `sanitized_env()` plus Schlüsselvariable des Agenten und Proxy-Variablen, `run_limited` mit Timeout und 2-MiB-Limit. Claude: `--tools ""`, `--permission-mode dontAsk`, `--no-session-persistence`, `--strict-mcp-config`, `--setting-sources ""`, `--disable-slash-commands`. Codex: `exec --sandbox read-only --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules -c mcp_servers={}`, Antwort aus `work/last.txt`. Der Preflight (`ai/check.py`) prüft den Anmeldestatus (`claude auth status`, `codex login status`, Exit 0 = angemeldet) im selben Temp-HOME, also mit der kopierten Datei wie beim echten Aufruf, und gibt die Statusausgabe (enthält die E-Mail) nicht weiter. Die Aufrufzeile ist in `settings.yaml` (`ai.agent.command`) überschreibbar. | `test_ai_providers.py` (`test_claude_runs_in_throwaway_home`, `test_codex_runs_in_throwaway_home_without_user_config`, `test_throwaway_home_removed_after_timeout`, `test_agent_gets_proxy_but_no_other_env`, `test_agent_output_limits_and_control_chars`, `test_agent_failures`) mit Attrappen-Programmen und Fake-HOME; `test_ai_check.py` |

Bekannte Grenzen und Restrisiken:

- Ein Schlüssel aus dem **Schlüsselbund** wird nicht maskiert: `known_keys` kennt nur Umgebungsvariablen. Er steht nur dann in einer Fehlermeldung, wenn der Anbieter ihn zurückspiegelt.
- Prompt-Injection über Hilfetexte, Moduldateien oder mitgesendete Ausgaben kann den Vorschlag beeinflussen. Wirkung nur auf Dateivorschläge oder Text, die der Nutzer im Diff sieht und freigeben muss; ausgeführt wird nichts. Wer den Diff ungelesen mit `--apply` übernimmt, übernimmt das Risiko (Module können eine Klasse senken; die Warnung erscheint, die Tool-Listen in `classify.py` bleiben, siehe 2.2).
- `--setting-sources ""` für Claude Code wurde nicht mit einem echten Aufruf getestet (nur `--help` und Doku, D-011); die Codex-Flags stützen sich nur auf die Dokumentation, Codex ist lokal nicht installiert.
- Restrisiko Codex: `--sandbox read-only` lässt Lesezugriff auf die ganze Platte; ein injizierter Prompt könnte Daten an den Anbieter senden, die die Datenvorschau nicht zeigt.
- Restrisiko Agenten-CLIs allgemein: Lokale Konfiguration wirkt nicht mehr (Temp-HOME), wohl aber Einstellungen, die der Anbieter serverseitig am Konto hält. Die Anmeldedaten selbst sind dem Agenten zugänglich (nötig für den Aufruf).
- Anmeldedaten: Auf dem Entwicklungsrechner (Linux) liegen sie als Datei `~/.claude/.credentials.json` (0600); mit dieser Kopie meldet `claude auth status` „loggedIn: true“. Liegen sie in einem Schlüsselbund (z. B. macOS-Keychain), fehlt die Datei: der Agent ist im Temp-HOME dann nicht angemeldet, der Preflight meldet das; Abhilfe `ANTHROPIC_API_KEY`. Ungeprüft: Erneuert der Agent im Temp-HOME ein OAuth-Token mit rotierendem Refresh-Token, verfällt die Kopie mit dem Löschen und das Original könnte ungültig werden (dann `claude login`).
- Die Datenvorschau zeigt, was **WhatTheShell** sendet; was ein Agent-Programm selbst nachlädt oder an den Anbieter schickt, zeigt sie nicht.

Ebenfalls geplant (Phase 7): eingebettetes Terminal (F-36). Vor der Umsetzung ist ein eigener Sicherheitsabschnitt zu schreiben und freizugeben.


- HTTP-Antworten der Provider werden auf 2 MiB begrenzt (`ai/providers/http.py`: `_send`, `get_json`, `post_json`); größere Antworten werden mit Fehler abgewiesen.

## 6. Meldung von Sicherheitsproblemen

Sicherheitsprobleme bitte als GitHub-Issue mit dem Label `security` melden, bis es eine eigene Adresse gibt. Keine Zugangsdaten, Secrets oder ausnutzbaren Details öffentlich posten, die Beschreibung der Art des Problems genügt, Details dann auf Nachfrage. Eine Antwortfrist ist nicht zugesagt (Ein-Personen-Projekt).
