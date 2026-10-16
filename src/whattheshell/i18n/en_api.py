# SPDX-License-Identifier: AGPL-3.0-or-later
"""English texts (key: German source string)."""

CATALOG: dict[str, str] = {
    # api/rest.py
    "Tool '{tool}' konnte nicht gelesen werden: {err}. Prüfe Rechte oder nutze refresh=1.": (
        "Tool '{tool}' could not be read: {err}. Check permissions or use refresh=1."
    ),
    "Kein Server registriert, der sich beenden lässt (kein `wts gui`).": (
        "No server registered that can be stopped (not running under `wts gui`)."
    ),
    "Ungültiger Subbefehl {bad!r}. Erlaubt: Buchstaben, Ziffern, _ und -, "
    "beginnend mit einem Buchstaben.": (
        "Invalid subcommand {bad!r}. Allowed: letters, digits, _ and -, starting with a letter."
    ),
    "Sandbox nicht verfügbar: {reason}": "Sandbox not available: {reason}",
    "Beispiel {index} gibt es nicht ({count} vorhanden).": (
        "Example {index} does not exist ({count} available)."
    ),
    "Zu viele Vorschauen gleichzeitig. Warte kurz und versuche es erneut.": (
        "Too many previews at once. Wait a moment and try again."
    ),
    "Sandbox konnte nicht starten. Prüfe /api/sandbox/selftest.": (
        "Sandbox could not start. Check /api/sandbox/selftest."
    ),
    # api/app.py
    "Ungültige Anfrage.": "Invalid request.",
    "Frontend nicht gebaut: cd gui && npm ci && npm run build": (
        "Frontend not built: cd gui && npm ci && npm run build"
    ),
    # api/security.py
    "Unzulässiger Host-Header. Erlaubt: 127.0.0.1 und localhost.": (
        "Host header not allowed. Allowed: 127.0.0.1 and localhost."
    ),
    "Token fehlt oder ist falsch. Öffne die URL von `wts gui`.": (
        "Token missing or wrong. Open the URL printed by `wts gui`."
    ),
    "Unzulässiger Origin. Anfragen nur von der eigenen Oberfläche.": (
        "Origin not allowed. Requests only from the app's own interface."
    ),
    "Anfrage zu groß (Grenze 1 MiB).": "Request too large (limit 1 MiB).",
    # api/workflows.py
    "Ungültige Workflow-id '{workflow_id}'. Erlaubt: Kleinbuchstaben, Ziffern, _ und -.": (
        "Invalid workflow id '{workflow_id}'. Allowed: lowercase letters, digits, _ and -."
    ),
    "Workflow '{workflow_id}' gibt es nicht.": "Workflow '{workflow_id}' does not exist.",
    "Workflow ist ungültig.": "Workflow is invalid.",
    "Workflow nicht schreibbar: {err}. Prüfe Rechte auf {folder}.": (
        "Workflow not writable: {err}. Check permissions on {folder}."
    ),
    "'{workflow_id}' liegt in der Quelle '{source}' ({path}) und ist "
    "hier nicht löschbar. Projektdateien gehören zum Projekt: "
    "dort von Hand entfernen.": (
        "'{workflow_id}' lives in source '{source}' ({path}) and cannot be deleted "
        "here. Project files belong to the project: remove them by hand there."
    ),
    "Workflow nicht löschbar: {err}.": "Workflow not deletable: {err}.",
    "Datei wurde außerhalb der App geändert. Prüfen und übernehmen.": (
        "File was changed outside the app. Review and accept it."
    ),
    "Ungültiger Dateiname '{filename}'. Erwartet: id{suffix} "
    "(Kleinbuchstaben, Ziffern, _ und -, ohne Pfad).": (
        "Invalid file name '{filename}'. Expected: id{suffix} "
        "(lowercase letters, digits, _ and -, no path)."
    ),
    "Inhalt ist kein gültiges UTF-8: {reason}.": "Content is not valid UTF-8: {reason}.",
    "Datei größer als {limit} Byte.": "File larger than {limit} bytes.",
    "'{filename}' gibt es im Nutzerordner schon. Mit overwrite=true ersetzen.": (
        "'{filename}' already exists in the user folder. Replace it with overwrite=true."
    ),
    "Stempel nicht schreibbar: {err}.": "Stamp not writable: {err}.",
    # api/settings_api.py
    "Einstellungen nicht schreibbar: {err}. Prüfe Rechte auf {folder}.": (
        "Settings not writable: {err}. Check permissions on {folder}."
    ),
    # api/modules_api.py
    "Für '{tool}' gibt es kein Modul. Mit POST /api/modules/scaffold entsteht ein Gerüst.": (
        "There is no module for '{tool}'. POST /api/modules/scaffold creates a skeleton."
    ),
    "Modul nicht lesbar: {err}. Prüfe Rechte auf {path}.": (
        "Module not readable: {err}. Check permissions on {path}."
    ),
    "Modul ist ungültig.": "Module is invalid.",
    "Das Modul beschreibt '{actual}', nicht '{tool}'. Passe 'tool:' an.": (
        "The module describes '{actual}', not '{tool}'. Adjust 'tool:'."
    ),
    "Modul nicht schreibbar: {err}. Prüfe Rechte auf {folder}.": (
        "Module not writable: {err}. Check permissions on {folder}."
    ),
    "'{tool}' ist mitgeliefert und nicht löschbar.": "'{tool}' is bundled and cannot be deleted.",
    "Für '{tool}' gibt es kein Nutzermodul.": "There is no user module for '{tool}'.",
    "Modul nicht löschbar: {err}.": "Module not deletable: {err}.",
    # api/ai_api.py
    "{path} nicht lesbar: {err}. Prüfe Rechte.": "{path} not readable: {err}. Check permissions.",
    "Zwei KI-Anfragen laufen bereits. Später erneut versuchen.": (
        "Two AI requests are already running. Try again later."
    ),
    "Anbieter fehlgeschlagen: {err}. Prüfe die Einstellungen (Anbieter, Schlüssel).": (
        "Provider failed: {err}. Check the settings (provider, key)."
    ),
    "tool ist '{actual}', erwartet '{expected}'": "tool is '{actual}', expected '{expected}'",
    "Modul nicht lesbar: {err}. Prüfe Rechte.": "Module not readable: {err}. Check permissions.",
    "Nicht schreibbar: {err}. Prüfe Rechte auf {folder}.": (
        "Not writable: {err}. Check permissions on {folder}."
    ),
    # api/runs.py
    "Interner Fehler: {err}": "Internal error: {err}",
    "Lauf '{run_id}' unbekannt": "Run '{run_id}' unknown",
    "cwd '{cwd}' muss ein existierender absoluter Ordner sein": (
        "cwd '{cwd}' must be an existing absolute folder"
    ),
    "Workflow ungültig": "Workflow invalid",
    "Laufordner nicht anlegbar: {err}": "Run folder could not be created: {err}",
    "Es laufen bereits {limit} Läufe. Einen abbrechen oder abwarten, dann erneut starten.": (
        "{limit} runs are already running. Abort one or wait, then start again."
    ),
    "Lauf '{run_id}' wurde bereits gestartet": "Run '{run_id}' was already started",
    "Keine offene Bestätigung für Schritt '{step_id}'": (
        "No open confirmation for step '{step_id}'"
    ),
    "Keine offene Abfrage für Schritt '{step_id}'": "No open question for step '{step_id}'",
    "Ungültige Nachricht: {reason}": "Invalid message: {reason}",
    # api/terminal.py
    "Kein offenes Terminal für diesen Lauf und Schritt.": "No open terminal for this run and step.",
    "Terminal ist schon verbunden (nur eine Verbindung).": (
        "Terminal is already connected (one connection only)."
    ),
    "Schon {limit} Terminals offen. Eines schließen.": (
        "{limit} terminals already open. Close one."
    ),
    "Kein freier Transkriptname für {run_id}-{step_id}.": (
        "No free transcript name for {run_id}-{step_id}."
    ),
    "Terminal nicht verfügbar: {reason} {hint}": "Terminal not available: {reason} {hint}",
    "Kein Terminal verbunden. Schritt im Browser öffnen und erneut starten.": (
        "No terminal connected. Open the step in the browser and start again."
    ),
    "Transkript nicht schreibbar: {err}. Platz und Rechte von {folder} prüfen.": (
        "Transcript not writable: {err}. Check space and permissions of {folder}."
    ),
    "Transkript nicht schreibbar": "Transcript not writable",
    "Eingabe-Rückstau über 1 MiB": "Input backlog over 1 MiB",
    "Terminal nimmt keine Eingaben an.": "Terminal does not accept input.",
    "Erwartet Binärdaten oder {type: resize, cols, rows}.": (
        "Expects binary data or {type: resize, cols, rows}."
    ),
    "Server wird beendet": "Server is shutting down",
    "15 Minuten ohne Ein- oder Ausgabe": "15 minutes without input or output",
    "Zeitlimit des Schritts erreicht": "Step time limit reached",
    "Erste Nachricht: {type: open, cols, rows}": "First message: {type: open, cols, rows}",
    "Terminal startet nicht: {err}": "Terminal does not start: {err}",
    "Terminal startet nicht": "Terminal does not start",
    "Ungültiger Transkriptname '{name}'. Erlaubt: Name aus der Liste.": (
        "Invalid transcript name '{name}'. Allowed: a name from the list."
    ),
    "Transkript '{name}' nicht gefunden.": "Transcript '{name}' not found.",
    # terminal/__init__.py
    "Ungültige Terminalgröße {cols}x{rows}: erlaubt sind 1 bis 65535.": (
        "Invalid terminal size {cols}x{rows}: allowed are 1 to 65535."
    ),
    "Kein Programm angegeben.": "No program given.",
    "Arbeitsverzeichnis {workdir} fehlt. Ordner anlegen oder cwd ändern.": (
        "Working directory {workdir} is missing. Create the folder or change cwd."
    ),
    "Umgebungsvariablen nicht erlaubt: {names}.": "Environment variables not allowed: {names}.",
    "Arbeitsverzeichnis {workdir} ist nicht aufgelöst; den bestätigten Pfad übergeben.": (
        "Working directory {workdir} is not resolved; pass the confirmed path."
    ),
    "setsid fehlt.": "setsid is missing.",
    "Installiere das Paket „util-linux“.": 'Install the package "util-linux".',
    "bwrap startet nicht: {err}.": "bwrap does not start: {err}.",
    # instance.py
    "{directory} gehört nicht dir oder ist für andere zugänglich. "
    "Ordner prüfen (chmod 700) oder XDG_RUNTIME_DIR setzen.": (
        "{directory} does not belong to you or is accessible to others. "
        "Check the folder (chmod 700) or set XDG_RUNTIME_DIR."
    ),
}
