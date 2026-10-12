// SPDX-License-Identifier: AGPL-3.0-or-later
const de = {
  "app.name": "WhatTheShell",
  "lang.label": "Sprache",
  "sandbox.ok": "Sandbox bereit",
  "sandbox.missing": "Sandbox nicht verfügbar",
  "sandbox.unknown": "Sandbox-Status unbekannt",
  "token.missing": "Bitte über `wts gui` starten. Die Adresse mit Sitzungstoken (#token=…) fehlt.",
  "catalog.title": "Katalog",
  "catalog.search": "Werkzeuge suchen",
  "catalog.favorites": "Favoriten",
  "catalog.other": "Weitere",
  "catalog.empty": "Keine Werkzeuge gefunden.",
  "catalog.loading": "Lade …",
  "catalog.fav.add": "{name} zu Favoriten hinzufügen",
  "catalog.fav.remove": "{name} aus Favoriten entfernen",
  "safety.safe": "sicher",
  "safety.caution": "Vorsicht",
  "safety.dangerous": "gefährlich",
  "canvas.title": "Arbeitsfläche",
  "canvas.placeholder": "Hier entsteht der Workflow-Editor.",
  "details.title": "Details",
  "details.placeholder": "Werkzeug im Katalog auswählen.",
  "details.usage": "Aufruf",
  "details.options": "Optionen",
  "details.subcommands": "Unterbefehle",
  "output.title": "Ausgabe",
  "output.show": "Ausgabe anzeigen",
  "output.hide": "Ausgabe ausblenden",
  "output.placeholder": "Noch keine Ausgabe.",
  "error.prefix": "Fehler",
  "stream.stdout": "stdout", "stream.stderr": "stderr", "stream.stdin": "stdin", "run.select": "Im Graph auswählen", "error.network": "Server nicht erreichbar: {message}",
  "port.in": "Eingang", "port.next": "Nächster Schritt", "port.then": "Dann", "port.else": "Sonst", "port.body": "Für jede Zeile", "port.fallback": "Ersatzschritte bei Fehler",
  "canvas.toolbar": "Werkzeugleiste", "canvas.new": "Neu", "canvas.name": "Name", "canvas.add.tool": "Hinzufügen: {name}", "canvas.add.pick": "Werkzeug im Katalog wählen",
  "canvas.delete": "Löschen", "canvas.flowHint": "Die Reihenfolge bleibt bestehen. Ziehe den Schritt stattdessen an einen anderen Anschluss, um sie zu ändern.",
  "kind.command": "Befehl", "kind.if": "Bedingung", "kind.foreach": "Schleife", "kind.set": "Variable setzen", "kind.wait": "Warten", "kind.message": "Meldung", "kind.abort": "Abbrechen",
  "history.undo": "Rückgängig", "history.redo": "Wiederholen",
  "vars.title": "Variablen", "vars.name": "Name", "vars.type": "Typ", "vars.default": "Standardwert", "vars.label": "Beschriftung", "vars.add": "Variable hinzufügen", "vars.remove": "Variable entfernen",
  "status.checking": "Prüfe …", "status.valid": "Workflow gültig", "status.invalid": "{n} Fehler im Workflow",
  "warn.duplicate": "Die id {a} existiert schon.", "warn.cycle": "{a} kann nicht in die eigene Teilfolge verschoben werden.", "warn.invalid": "Ungültige id {a}.",
  "warn.path": "Zielfolge nicht gefunden.", "warn.pipe": "Pipe von {b} in {a} entfernt: nur frühere Schritte sind erlaubt.",
  "step.id": "Schritt-id", "step.rename": "Umbenennen", "step.label": "Beschriftung", "step.sub": "Unterbefehl", "step.inputs": "Eingaben", "step.options": "Optionen", "step.rare": "Selten",
  "step.search": "Optionen durchsuchen", "step.extra": "Freie Argumente", "step.extra.help": "Eine Zeile je Argument, wird unverändert angehängt.",
  "step.stdin": "Standardeingabe", "step.cwd": "Arbeitsordner", "step.okcodes": "Erfolgs-Exitcodes (kommagetrennt)", "step.timeout": "Zeitlimit (Sekunden)", "step.onerror": "Bei Fehler",
  "stdin.none": "keine", "stdin.pipe": "Pipe von Schritt", "stdin.text": "Text", "stdin.file": "Datei",
  "onerror.abort": "abbrechen", "onerror.continue": "weitermachen", "onerror.retry": "wiederholen", "onerror.fallback": "Ersatzschritte", "onerror.retries": "Anzahl Wiederholungen",
  "field.path.placeholder": "Pfad relativ zum Arbeitsordner", "field.required": "Pflichtfeld", "field.guessed": "geraten", "field.guessed.title": "Vom Hilfe-Parser geraten, per Modul korrigierbar",
  "field.template": "Enthält eine Vorlage: keine Typprüfung.", "field.more": "Mehr",
  "cond.source": "Quelle", "cond.operator": "Operator", "cond.value": "Wert", "cond.true": "ja",
  "op.eq": "ist gleich", "op.ne": "ist ungleich", "op.contains": "enthält", "op.regex": "passt auf Regex", "op.is_empty": "ist leer", "op.line_count_gt": "Zeilenzahl größer", "op.line_count_eq": "Zeilenzahl gleich",
  "op.number_gt": "Zahl größer", "op.number_lt": "Zahl kleiner", "op.number_eq": "Zahl gleich", "op.json_path": "JSON-Pfad", "op.file_exists": "Datei existiert",
  "foreach.as": "Name des Elements", "set.variable": "Variable", "set.value": "Wert", "wait.seconds": "Sekunden", "message.text": "Text", "abort.exit": "Exitcode",
  "cmd.title": "Befehl", "cmd.copy": "Kopieren", "cmd.copied": "Kopiert", "cmd.safety": "Sicherheitsklasse",
  "prev.title": "Vorschau", "prev.example": "Beispiel", "prev.none": "ohne Beispieldaten", "prev.run": "Beispiel ausführen", "prev.exit": "Exitcode", "prev.duration": "Dauer",
  "prev.truncated": "Ausgabe gekürzt", "prev.timeout": "Zeitlimit erreicht", "prev.sandbox": "Sandbox nicht verfügbar", "prev.retest": "Erneut testen", "prev.applied": "Beispielwerte übernommen",
  "run.dry": "Trockenlauf", "run.execute": "Ausführen", "run.pause": "Pause", "run.resume": "Weiter", "run.step": "Einzelschritt", "run.abort": "Abbrechen",
  "run.status.idle": "Bereit", "run.status.running": "Läuft", "run.status.success": "Erfolgreich beendet", "run.status.failed": "Fehlgeschlagen", "run.status.aborted": "Abgebrochen",
  "run.lost": "Verbindung zum Lauf verloren.", "run.history": "Verlauf laden", "run.plan": "Plan", "run.ok": "ok", "run.failed": "Fehler", "run.skipped": "übersprungen",
  "run.capture": "Als Variable übernehmen", "run.evaluate": "Hier auswerten",
  "run.dialog": "Workflow ausführen?", "run.maxsafety": "Höchste Sicherheitsklasse", "run.cwd.effective": "Arbeitsordner", "run.cwd.server": "wird vom Server gewählt",
  "run.cwd.placeholder": "leer = Server wählt; sonst absoluter Pfad", "run.cancel": "Abbrechen", "run.confirm": "Workflow ausführen",
  "run.confirm.title": "Schritt bestätigen", "run.reject": "Ablehnen", "run.accept": "Ausführen",
  "file.menu": "Datei", "file.open": "Öffnen", "file.save": "Speichern", "file.saveas": "Speichern unter", "file.delete": "Löschen", "file.untitled": "Unbenannt",
  "file.dirty": "ungespeichert", "file.none": "Keine Workflows gefunden.", "file.source.bundled": "mitgeliefert", "file.source.user": "eigene",
  "file.discard": "Ungespeicherte Änderungen verwerfen?", "file.delete.confirm": "„{name}“ löschen?", "file.overwrite": "„{id}“ existiert schon. Überschreiben?",
  "file.id": "Dateiname (id)", "file.id.help": "Kleinbuchstaben, Ziffern, - und _; beginnt mit Buchstabe oder Ziffer.",
  "canvas.target": "Ziel", "canvas.target.end": "ans Ende", "canvas.target.then": "in „Dann“", "canvas.target.else": "in „Sonst“", "canvas.target.body": "in „Schleife“",
};
const en: Record<keyof typeof de, string> = {
  "app.name": "WhatTheShell",
  "lang.label": "Language",
  "sandbox.ok": "Sandbox ready",
  "sandbox.missing": "Sandbox unavailable",
  "sandbox.unknown": "Sandbox status unknown",
  "token.missing": "Please start via `wts gui`. The address with the session token (#token=…) is missing.",
  "catalog.title": "Catalog",
  "catalog.search": "Search tools",
  "catalog.favorites": "Favorites",
  "catalog.other": "Other",
  "catalog.empty": "No tools found.",
  "catalog.loading": "Loading …",
  "catalog.fav.add": "Add {name} to favorites",
  "catalog.fav.remove": "Remove {name} from favorites",
  "safety.safe": "safe",
  "safety.caution": "caution",
  "safety.dangerous": "dangerous",
  "canvas.title": "Canvas",
  "canvas.placeholder": "The workflow editor will live here.",
  "details.title": "Details",
  "details.placeholder": "Select a tool in the catalog.",
  "details.usage": "Usage",
  "details.options": "Options",
  "details.subcommands": "Subcommands",
  "output.title": "Output",
  "output.show": "Show output",
  "output.hide": "Hide output",
  "output.placeholder": "No output yet.",
  "error.prefix": "Error",
  "stream.stdout": "stdout", "stream.stderr": "stderr", "stream.stdin": "stdin", "run.select": "Select in graph", "error.network": "Server unreachable: {message}",
  "port.in": "Input", "port.next": "Next step", "port.then": "Then", "port.else": "Else", "port.body": "For each line", "port.fallback": "Fallback steps on error",
  "canvas.toolbar": "Toolbar", "canvas.new": "New", "canvas.name": "Name", "canvas.add.tool": "Add: {name}", "canvas.add.pick": "Pick a tool in the catalog",
  "canvas.delete": "Delete", "canvas.flowHint": "The order stays. Drag the step to another port to change it.",
  "kind.command": "Command", "kind.if": "If", "kind.foreach": "Loop", "kind.set": "Set variable", "kind.wait": "Wait", "kind.message": "Message", "kind.abort": "Abort",
  "history.undo": "Undo", "history.redo": "Redo",
  "vars.title": "Variables", "vars.name": "Name", "vars.type": "Type", "vars.default": "Default", "vars.label": "Label", "vars.add": "Add variable", "vars.remove": "Remove variable",
  "status.checking": "Checking …", "status.valid": "Workflow valid", "status.invalid": "{n} errors in workflow",
  "warn.duplicate": "The id {a} already exists.", "warn.cycle": "{a} cannot be moved into its own sub-sequence.", "warn.invalid": "Invalid id {a}.",
  "warn.path": "Target sequence not found.", "warn.pipe": "Pipe from {b} into {a} removed: only earlier steps are allowed.",
  "step.id": "Step id", "step.rename": "Rename", "step.label": "Label", "step.sub": "Subcommand", "step.inputs": "Inputs", "step.options": "Options", "step.rare": "Rare",
  "step.search": "Search options", "step.extra": "Free arguments", "step.extra.help": "One line per argument, appended unchanged.",
  "step.stdin": "Standard input", "step.cwd": "Working directory", "step.okcodes": "Success exit codes (comma separated)", "step.timeout": "Timeout (seconds)", "step.onerror": "On error",
  "stdin.none": "none", "stdin.pipe": "Pipe from step", "stdin.text": "Text", "stdin.file": "File",
  "onerror.abort": "abort", "onerror.continue": "continue", "onerror.retry": "retry", "onerror.fallback": "fallback steps", "onerror.retries": "Number of retries",
  "field.path.placeholder": "Path relative to the working directory", "field.required": "required", "field.guessed": "guessed", "field.guessed.title": "Guessed by the help parser, can be corrected by a module",
  "field.template": "Contains a template: no type check.", "field.more": "More",
  "cond.source": "Source", "cond.operator": "Operator", "cond.value": "Value", "cond.true": "yes",
  "op.eq": "equals", "op.ne": "does not equal", "op.contains": "contains", "op.regex": "matches regex", "op.is_empty": "is empty", "op.line_count_gt": "line count greater", "op.line_count_eq": "line count equals",
  "op.number_gt": "number greater", "op.number_lt": "number less", "op.number_eq": "number equals", "op.json_path": "JSON path", "op.file_exists": "file exists",
  "foreach.as": "Element name", "set.variable": "Variable", "set.value": "Value", "wait.seconds": "Seconds", "message.text": "Text", "abort.exit": "Exit code",
  "cmd.title": "Command", "cmd.copy": "Copy", "cmd.copied": "Copied", "cmd.safety": "Safety class",
  "prev.title": "Preview", "prev.example": "Example", "prev.none": "without example data", "prev.run": "Run example", "prev.exit": "Exit code", "prev.duration": "Duration",
  "prev.truncated": "output truncated", "prev.timeout": "timed out", "prev.sandbox": "Sandbox unavailable", "prev.retest": "Test again", "prev.applied": "Example values applied",
  "run.dry": "Dry run", "run.execute": "Run", "run.pause": "Pause", "run.resume": "Resume", "run.step": "Single step", "run.abort": "Abort",
  "run.status.idle": "Ready", "run.status.running": "Running", "run.status.success": "Finished successfully", "run.status.failed": "Failed", "run.status.aborted": "Aborted",
  "run.lost": "Connection to the run lost.", "run.history": "Load history", "run.plan": "Plan", "run.ok": "ok", "run.failed": "failed", "run.skipped": "skipped",
  "run.capture": "Keep as variable", "run.evaluate": "Evaluate here",
  "run.dialog": "Run workflow?", "run.maxsafety": "Highest safety class", "run.cwd.effective": "Working directory", "run.cwd.server": "chosen by the server",
  "run.cwd.placeholder": "empty = server chooses; otherwise absolute path", "run.cancel": "Cancel", "run.confirm": "Run workflow",
  "run.confirm.title": "Confirm step", "run.reject": "Reject", "run.accept": "Run",
  "file.menu": "File", "file.open": "Open", "file.save": "Save", "file.saveas": "Save as", "file.delete": "Delete", "file.untitled": "Untitled",
  "file.dirty": "unsaved", "file.none": "No workflows found.", "file.source.bundled": "bundled", "file.source.user": "own",
  "file.discard": "Discard unsaved changes?", "file.delete.confirm": "Delete “{name}”?", "file.overwrite": "“{id}” already exists. Overwrite?",
  "file.id": "File name (id)", "file.id.help": "Lowercase letters, digits, - and _; starts with a letter or digit.",
  "canvas.target": "Target", "canvas.target.end": "at the end", "canvas.target.then": "into “Then”", "canvas.target.else": "into “Else”", "canvas.target.body": "into “Loop”",
};

export type Lang = "de" | "en";
const dicts: Record<Lang, Record<string, string>> = { de, en };

function detect(): Lang {
  const stored = typeof localStorage === "undefined" ? null : localStorage.getItem("wts.lang");
  if (stored === "de" || stored === "en") return stored;
  const nav = typeof navigator === "undefined" ? "de" : navigator.language;
  return nav.toLowerCase().startsWith("en") ? "en" : "de";
}

let lang: Lang = detect();

export const getLang = (): Lang => lang;

export function setLang(next: Lang): void {
  lang = next;
  try {
    if (typeof localStorage !== "undefined") localStorage.setItem("wts.lang", next);
  } catch {
    /* storage unavailable (private mode): the choice just lasts for this session */
  }
}

/** Translate `key`; unknown keys return the key itself. `{name}` placeholders come from `params`. */
export function t(key: string, params?: Record<string, string | number>): string {
  const text = dicts[lang][key];
  if (text === undefined) {
    if (import.meta.env?.DEV) console.warn(`i18n: missing key "${key}"`);
    return key;
  }
  return params ? text.replace(/\{(\w+)\}/g, (m, k: string) => String(params[k] ?? m)) : text;
}
