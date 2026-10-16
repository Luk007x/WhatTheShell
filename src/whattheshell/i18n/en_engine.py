# SPDX-License-Identifier: AGPL-3.0-or-later
"""English texts (key: German source string)."""

CATALOG: dict[str, str] = {
    # argv.py
    "Feld '{field}': {problem}. {hint}": "Field '{field}': {problem}. {hint}",
    "Wert ist kein Wahrheitswert (Typ bool)": "value is not a boolean (type bool)",
    "Erwartet: true oder false": "Expected: true or false",
    "erwartet eine Liste": "expects a list",
    "Mehrfachfeld als Liste angeben": "Give a multi-value field as a list",
    "Option hat kein Flag": "option has no flag",
    "Modul oder Katalog prüfen": "Check the module or catalog",
    "Option '{id}' erwartet einen einzelnen Wert, bekam Liste. Einzelwert angeben": (
        "Option '{id}' expects a single value, got a list. Give a single value"
    ),
    "Pflichteingabe fehlt": "required input is missing",
    "Wert angeben": "Enter a value",
    "Unbekanntes Feld '{key}' für {tool}, bekannte Felder: {known}": (
        "Unknown field '{key}' for {tool}, known fields: {known}"
    ),
    "Wert ist nicht erlaubt (Typ {type})": "value is not allowed (type {type})",
    "Erlaubt: {choices}": "Allowed: {choices}",
    "erwartet {expected} Werte je Vorkommen, erhalten {got}": (
        "expects {expected} values per occurrence, got {got}"
    ),
    "Liste mit passender Länge angeben": "Give a list of the right length",
    "Wert ist keine Zahl": "value is not a number",
    "Erwartet: {type}": "Expected: {type}",
    # evaluate.py
    "Pfad '{path}' liegt außerhalb des Arbeitsverzeichnisses": (
        "Path '{path}' is outside the working directory"
    ),
    "Keine Zahl in '{source}' gefunden": "No number found in '{source}'",
    "'{source}' ist kein gültiges JSON: {err}": "'{source}' is not valid JSON: {err}",
    "Datei '{file}' aus '{source}' existiert nicht": (
        "File '{file}' from '{source}' does not exist"
    ),
    "Datei '{file}' nicht lesbar: {err}": "File '{file}' is not readable: {err}",
    # plan.py
    "{tool} (Argumente noch nicht prüfbar: {err})": (
        "{tool} (arguments cannot be checked yet: {err})"
    ),
    "Abfrage „{title}“: {fields}, Knöpfe: {buttons}": (
        'Prompt "{title}": {fields}, buttons: {buttons}'
    ),
    "interaktiv, wird im Trockenlauf übersprungen: {text}": (
        "interactive, skipped in the dry run: {text}"
    ),
    "{source} als {name}": "{source} as {name}",
    # runner.py
    "Terminal-Schritt: cwd muss innerhalb von {root} liegen (ist: {cwd})": (
        "Terminal step: cwd must be inside {root} (is: {cwd})"
    ),
    "Terminal-Schritte laufen nur in `wts gui`. Workflow dort starten.": (
        "Terminal steps only run in `wts gui`. Start the workflow there."
    ),
    "Variable '{name}': '{value}' ist keine erlaubte Auswahl ({choices}). "
    "Einen dieser Werte angeben.": (
        "Variable '{name}': '{value}' is not an allowed choice ({choices}). "
        "Give one of these values."
    ),
    "Variable '{name}': Wert passt nicht zum Muster '{pattern}'. Wert korrigieren.": (
        "Variable '{name}': value does not match the pattern '{pattern}'. Correct the value."
    ),
    "interaktiv": "interactive",
    "setzt Umgebungsvariablen": "sets environment variables",
    "Arbeitsverzeichnis außerhalb des Workflow-Ordners": (
        "working directory outside the workflow folder"
    ),
    "liest Datei außerhalb": "reads a file outside",
    "Zu viele ungültige Antworten bei Abfrage '{id}'": (
        "Too many invalid answers to prompt '{id}'"
    ),
    "Schritt '{id}' fehlgeschlagen: {reason}": "Step '{id}' failed: {reason}",
    "Exit-Code {code}, erlaubt: {allowed}": "exit code {code}, allowed: {allowed}",
    "Variable '{name}': Wert passt nicht zu Typ {kind} (true oder false). Wert korrigieren.": (
        "Variable '{name}': value does not match type {kind} (true or false). Correct the value."
    ),
    "Variable '{name}': Wert passt nicht zu Typ {kind}. Wert korrigieren.": (
        "Variable '{name}': value does not match type {kind}. Correct the value."
    ),
    "Variable '{name}': {value} ist kleiner als das Minimum {limit}.": (
        "Variable '{name}': {value} is below the minimum {limit}."
    ),
    "Variable '{name}': {value} ist größer als das Maximum {limit}.": (
        "Variable '{name}': {value} is above the maximum {limit}."
    ),
    "Netzzugang": "network access",
    "Unbekannte Variable(n): {unknown}. Deklariert: {declared}.": (
        "Unknown variable(s): {unknown}. Declared: {declared}."
    ),
    "keine": "none",
    "Abfrage-Schritt braucht die Oberfläche oder ein Terminal.": (
        "A prompt step needs the GUI or a terminal."
    ),
    "Unbekannter Knopf '{button}'. Einen der Knöpfe wählen.": (
        "Unknown button '{button}'. Choose one of the buttons."
    ),
    "Schritt '{id}' vom Nutzer abgelehnt": "Step '{id}' rejected by the user",
    "Programm '{program}' konnte nicht gestartet werden (Rechte, Format?)": (
        "Program '{program}' could not be started (permissions, format?)"
    ),
    "Ungültiges Argument oder Umgebung: {err}": "Invalid argument or environment: {err}",
    "Zeitlimit überschritten": "Time limit exceeded",
    "Ausgabelimit von {limit} Bytes überschritten": "Output limit of {limit} bytes exceeded",
    "Abgebrochen": "Aborted",
    "Terminal konnte nicht gestartet werden: {err}": "Terminal could not be started: {err}",
    "Schritt '{id}': {err}": "Step '{id}': {err}",
    "Workflow abgeschlossen": "Workflow finished",
    "Bedingung von '{id}' wählt {branch}": "Condition of '{id}' selects {branch}",
    "Keine Antwort innerhalb von {n} s": "No answer within {n} s",
    "Abfrage '{id}' vom Nutzer abgebrochen": "Prompt '{id}' cancelled by the user",
    "Arbeitsverzeichnis '{cwd}' existiert nicht": "Working directory '{cwd}' does not exist",
    "stdin.pipe '{pipe}': Schritt hat keine Ausgabe (nicht gelaufen?)": (
        "stdin.pipe '{pipe}': step has no output (not run yet?)"
    ),
    "stdin.file '{path}' nicht lesbar: {err}": "stdin.file '{path}' is not readable: {err}",
    "Schritt '{id}' fehlgeschlagen ({reason}), weiter": (
        "Step '{id}' failed ({reason}), continuing"
    ),
    "Schritt '{id}' fehlgeschlagen ({reason}), Ersatzschritte": (
        "Step '{id}' failed ({reason}), running fallback steps"
    ),
    "Schritt '{id}': Tool '{tool}' konnte nicht gelesen werden: {err}": (
        "Step '{id}': tool '{tool}' could not be read: {err}"
    ),
    "Quelle von '{id}' ist leer": "Source of '{id}' is empty",
    "Pflichtvariable '{name}' hat keinen Wert. Wert eingeben.": (
        "Required variable '{name}' has no value. Enter a value."
    ),
    "Pflichtvariable '{name}' hat keinen Wert. Mit --var {name}=WERT angeben.": (
        "Required variable '{name}' has no value. Give it with --var {name}=VALUE."
    ),
    "Schritt '{id}': Bedingung: {err}": "Step '{id}': condition: {err}",
    "Schritt '{id}': Quelle: {err}": "Step '{id}': source: {err}",
    "Workflow abgebrochen": "Workflow aborted",
    "WARNUNG: Umgebungsvariable '{key}' nicht erlaubt, verworfen": (
        "WARNING: environment variable '{key}' not allowed, discarded"
    ),
    # template.py
    "Unbekanntes Feld '{field}' in '{ref}', erlaubt: stdout|stderr|exit_code|lines": (
        "Unknown field '{field}' in '{ref}', allowed: stdout|stderr|exit_code|lines"
    ),
    "Unbekannte Referenz '{ref}': hier ist kein foreach-Element sichtbar": (
        "Unknown reference '{ref}': no foreach item is visible here"
    ),
    "Unbekannter Schritt '{step}' in '{ref}': noch nicht gelaufen?": (
        "Unknown step '{step}' in '{ref}': not run yet?"
    ),
    "Unbekannte Variable '{name}' in '{ref}'": "Unknown variable '{name}' in '{ref}'",
    "Ungültiges Template in {text}: '{{{{' ohne gültige Referenz": (
        "Invalid template in {text}: '{{{{' without a valid reference"
    ),
    "Variable '{name}' hat noch keinen Wert (wird erst durch einen Abfrage-Schritt gesetzt).": (
        "Variable '{name}' has no value yet (it is only set by a prompt step)."
    ),
    # models
    "Pfad muss relativ sein, nicht leer und ohne '..'": (
        "Path must be relative, not empty and without '..'"
    ),
    "Dokument muss ein Objekt (Mapping) sein, gefunden: {type}": (
        "Document must be an object (mapping), found: {type}"
    ),
    "Feld schema_version fehlt, erwartet {expected}": (
        "Field schema_version is missing, expected {expected}"
    ),
    "schema_version muss eine ganze Zahl >= 1 sein, ist {version}": (
        "schema_version must be an integer >= 1, is {version}"
    ),
    "schema_version {version} ist neuer als unterstützt ({supported}); App aktualisieren": (
        "schema_version {version} is newer than supported ({supported}); update the app"
    ),
    "inputs/options-id": "inputs/options id",
    "subcommand-name": "subcommand name",
    "stdout_regex ist kein gültiger regulärer Ausdruck: {err}": (
        "stdout_regex is not a valid regular expression: {err}"
    ),
    "{kind} '{value}' kommt mehrfach vor": "{kind} '{value}' occurs more than once",
    "(Eingabe: {value})": "(input: {value})",
    "'{value}' ist reserviert": "'{value}' is reserved",
    "Schritt '{id}': Referenz '{ref}' {why}": "Step '{id}': reference '{ref}' {why}",
    "Schritt '{id}' setzt undeklarierte Variable '{name}'": (
        "Step '{id}' sets undeclared variable '{name}'"
    ),
    "stdin: genau eines von pipe, text, file setzen": "stdin: set exactly one of pipe, text, file",
    "condition: genau ein Operator erlaubt, gesetzt: {given}": (
        "condition: exactly one operator allowed, set: {given}"
    ),
    "keiner": "none",
    "on_error: retries ist genau bei action=retry Pflicht": (
        "on_error: retries is required exactly when action=retry"
    ),
    "on_error: steps ist genau bei action=fallback Pflicht": (
        "on_error: steps is required exactly when action=fallback"
    ),
    "ask: fields enthält doppelte Namen": "ask: fields contains duplicate names",
    "ask: buttons enthält doppelte Einträge": "ask: buttons contains duplicate entries",
    "ask: button_variable darf nicht auch in fields stehen": (
        "ask: button_variable must not also be in fields"
    ),
    "Variable vom Typ secret darf keinen default haben": (
        "A variable of type secret must not have a default"
    ),
    "choices ist nur bei type enum erlaubt": "choices is only allowed for type enum",
    "min und max sind nur bei type int oder float erlaubt": (
        "min and max are only allowed for type int or float"
    ),
    "Schritt '{id}' braucht `kind` oder `tool`": "Step '{id}' needs `kind` or `tool`",
    "pattern ist nur bei type string oder path erlaubt": (
        "pattern is only allowed for type string or path"
    ),
    "pattern: höchstens 500 Zeichen erlaubt": "pattern: at most 500 characters allowed",
    "Schritt-id '{id}' kommt mehrfach vor": "Step id '{id}' occurs more than once",
    "Schritt '{id}': as '{name}' überdeckt eine Schritt-id": (
        "Step '{id}': as '{name}' shadows a step id"
    ),
    "Schritt '{id}': pipe-Quelle {pipe} ist ein Terminal-Schritt und hat keine Ausgabe": (
        "Step '{id}': pipe source {pipe} is a terminal step and has no output"
    ),
    "ist außerhalb eines passenden foreach unbekannt": ("is unknown outside a matching foreach"),
    "Schritt '{id}': Feld '{name}' ist keine deklarierte Variable": (
        "Step '{id}': field '{name}' is not a declared variable"
    ),
    "Schritt '{id}': ungültiges Template in {text}": "Step '{id}': invalid template in {text}",
    "regex ist kein gültiger regulärer Ausdruck: {err}": (
        "regex is not a valid regular expression: {err}"
    ),
    "pattern: ungültiger regulärer Ausdruck ({err})": "pattern: invalid regular expression ({err})",
    "Schritt '{id}': button_variable '{name}' muss eine deklarierte Variable vom Typ string "
    "oder enum sein": (
        "Step '{id}': button_variable '{name}' must be a declared variable of type string or enum"
    ),
    "nennt keine deklarierte Variable": "does not name a declared variable",
    "(stdin.pipe) ist kein vorheriger Schritt": "(stdin.pipe) is not a previous step",
    "muss auf {fields} enden": "must end in {fields}",
    "zeigt auf '{head}', der nicht vorher steht": "points to '{head}', which does not come before",
    "ist unbekannt": "is unknown",
    # settings.py
    "Erlaubte Flags: {flags}": "Allowed flags: {flags}",
    "Wert {value} für {flag} nicht erlaubt (erlaubt: {allowed})": (
        "Value {value} for {flag} not allowed (allowed: {allowed})"
    ),
    "Modellname {value} ungültig": "Model name {value} is invalid",
    "{flag} erwartet eine ganze Zahl": "{flag} expects an integer",
    "-c {value} nicht erlaubt (Schlüssel: {keys})": "-c {value} not allowed (keys: {keys})",
    "Erstes Element muss genau `{kind}` sein. {hint}": (
        "First element must be exactly `{kind}`. {hint}"
    ),
    "`exec` muss direkt auf `codex` folgen. {hint}": "`exec` must directly follow `codex`. {hint}",
    "Pflichtteil `-c mcp_servers={}` fehlt (hält MCP-Server aus)": (
        "Required part `-c mcp_servers={}` is missing (keeps MCP servers off)"
    ),
    "key_env erwartet den NAMEN einer Umgebungsvariable (z. B. ANTHROPIC_API_KEY), "
    "nicht den Schlüssel selbst": (
        "key_env expects the NAME of an environment variable (e.g. ANTHROPIC_API_KEY), "
        "not the key itself"
    ),
    "Element {flag} nicht erlaubt. {hint}": "Element {flag} not allowed. {hint}",
    "Flag {flag} doppelt. {hint}": "Flag {flag} given twice. {hint}",
    "Pflichtteil `{part}` fehlt (hält Werkzeuge und Konfiguration aus)": (
        "Required part `{part}` is missing (keeps tools and configuration off)"
    ),
    "Feld `ai.agent.command` wird nicht mehr unterstützt. "
    "Modell und Reasoning in den Einstellungen wählen.": (
        "Field `ai.agent.command` is no longer supported. "
        "Choose model and reasoning in the settings."
    ),
    "{flag} braucht einen Wert. {hint}": "{flag} needs a value. {hint}",
    "{problem}. {hint}": "{problem}. {hint}",
    "Feld '{name}' nicht erlaubt: Schlüssel gehören nie in diese Datei. "
    "Nur der Name der Umgebungsvariable (key_env) oder key_source: keyring.": (
        "Field '{name}' not allowed: keys never belong in this file. "
        "Only the name of the environment variable (key_env) or key_source: keyring."
    ),
}
