# Fehlerbehebung

## Wo liegen die Logs

| Was | Wo |
|---|---|
| Server, der mit `wts gui start` im Hintergrund läuft | `~/.cache/whattheshell/gui.log` |
| Server im Vordergrund (`wts gui`) | Ausgabe im Terminal |
| Zugriffe | Es gibt kein Zugriffslog (damit das Token nicht in einem Log landet) |

Fehlermeldungen der Oberfläche nennen Ursache und Lösungshinweis. Stacktraces stehen nicht in den Antworten, sondern nur im Log.

## Sandbox und Installation

### „Sandbox nicht verfügbar“ / bubblewrap fehlt

Ohne `bwrap` gibt es keine Vorschau, keine Modul-Beispiele und keine Terminal-Schritte; es gibt keinen ungeschützten Ersatz.

1. `wts sandbox` ausführen. Die Ausgabe nennt den Grund und den Installationsbefehl der Distribution, z. B. `sudo apt install bubblewrap`.
2. In der Oberfläche „Erneut testen“ wählen (im Bereich „Vorschau“).
3. Fehlt `prlimit` oder `setsid`, das Paket `util-linux` installieren. Ohne `prlimit` läuft die Sandbox mit Warnung ohne Speicher- und Prozesslimit.
4. Ist `bwrap` installiert, die Sandbox aber nicht verfügbar, sind meist unprivilegierte User-Namespaces gesperrt (AppArmor oder Systemeinstellung). Das lässt sich nur auf Systemebene ändern.

### Terminal-Schritt startet nicht

Ohne Sandbox startet der Schritt nicht; es erscheint eine Meldung mit dem Installationshinweis (Exit-Code 126). Siehe oben.

## Start und Verbindung

### „Läuft bereits auf Port N (PID P)“

Eine Instanz läuft schon. `wts gui start` oder `wts gui` öffnet dann nur den Browser. Ein zweiter Server wird nicht gestartet. Zustand prüfen:

```
wts gui status        # Exit-Code 3: nicht gestartet
wts gui stop          # beenden
```

Lässt sich der Prozess nicht beenden, nennt `wts gui stop` den Befehl `kill -9 PID`. Bei „Läuft bereits (Zustand noch nicht lesbar)“ kurz warten und `wts gui status` wiederholen.

### „Bitte über `wts gui` starten. Die Adresse mit Sitzungstoken (#token=…) fehlt.“

Die Seite wurde ohne Token geöffnet, z. B. über ein Lesezeichen oder nach einem Neustart des Servers (das Token ändert sich bei jedem Start). Lösung: `wts gui start` aufrufen. Das öffnet den Browser mit einer gültigen Adresse. Läuft der Server im Vordergrund (`wts gui`), steht die Adresse mit Token in der Terminalausgabe.

### „Port N nicht nutzbar“

Der angegebene Port ist belegt oder nicht erlaubt. Einen anderen mit `--port` wählen oder `--port` weglassen (dann wird ein freier Port gewählt).

### „Server nicht gestartet. Ursache im Log: …“

`wts gui start` hat nach 10 Sekunden keinen laufenden Server gefunden. Der Grund steht in `~/.cache/whattheshell/gui.log`. Alternativ `wts gui` im Vordergrund starten, dann erscheinen die Meldungen im Terminal.

### „Start als root wird verweigert“

Die Oberfläche kann Befehle ausführen und startet deshalb nicht als root. Als normaler Benutzer starten.

### „Server nicht erreichbar: …“

Der Server wurde beendet (z. B. mit `wts gui stop` oder „WhatTheShell beenden“). Neu starten mit `wts gui start`.

### „Verbindung zum Lauf verloren.“

Die Seite hat die Verbindung zum Server verloren; der Server läuft eventuell nicht mehr. `wts gui status` prüfen und gegebenenfalls neu starten. Läufe sind nach einem Neustart des Servers weg.

### „Zustandsdatei nicht geschrieben“ / „Instanzsperre nicht möglich“

Der Ordner für den Zustand (`$XDG_RUNTIME_DIR/whattheshell` oder `~/.cache/whattheshell/run`) ist nicht beschreibbar oder hat falsche Rechte. Rechte prüfen; der Ordner muss dem Benutzer gehören.

## Workflows

### „Datei wurde außerhalb der App geändert“ / Workflow startet nicht

Der Workflow ist „Außerhalb geändert“ oder „Nicht geprüft“ (siehe „Bibliothek: Filter, Import und Integrität“ im Kapitel „Workflow bauen“). Die Datei ansehen, dann in der Bibliothek „Prüfen und übernehmen“ klicken oder `wts workflows accept ID` bzw. `wts run --accept` verwenden. Ein Trockenlauf geht ohne Übernahme. Nach einem Update zeigen vorhandene eigene Dateien einmalig „Nicht geprüft“. Dateien außerhalb der Workflow-Ordner brauchen immer `--accept`.

### Workflow ungültig

In der Oberfläche steht „n Fehler im Workflow“; die Meldung nennt das Feld. Auf der Kommandozeile:

```
wts validate DATEI
```

Typische Ursachen:

- Doppelte oder ungültige id (`die id X existiert schon`, `Ungültige id X`): ids bestehen aus Kleinbuchstaben, Ziffern und `_` und beginnen mit einem Buchstaben.
- Eine Vorlage `{{ … }}` verweist auf einen Schritt, der später kommt oder nicht existiert, oder auf eine nicht deklarierte Variable.
- Eine Bedingung hat keinen oder mehrere Operatoren: genau einer ist erlaubt.
- Unbekannte Felder (Tippfehler). Die Meldung nennt den Feldpfad.
- Kaputte Dateien erscheinen in der Bibliothek ausgegraut mit `Pfad:Zeile: Meldung`. Die Datei korrigieren; die Liste lädt sich neu.

### Variable passt nicht zum Muster

Beim Start: „Passt nicht zum Muster …“. Das Feld zeigt „Muster: …“. Der Regex muss den ganzen Wert treffen, nicht nur einen Teil. Beim Workflow „WLAN auf 5 GHz fixieren“ muss die BSSID z. B. dem Format `AA:BB:CC:DD:EE:FF` entsprechen.

Weitere Meldungen: „Pflichtfeld“, „Ganze Zahl erwartet“, „Zahl erwartet“, „Wert aus der Liste wählen“, „Mindestens N“, „Höchstens N“.

### „--var erwartet NAME=WERT“

Variablen werden bei `wts run` als `--var name=wert` übergeben, z. B. `--var logdir=./logs`.

### „Bestätigung nötig, aber kein Terminal“

`wts run` hat riskante Schritte gefunden und kann nicht nachfragen (z. B. in einem Skript). Mit `--yes` bestätigen oder zuerst mit `--dry-run` prüfen (Exit-Code 2).

### „Tool … nicht auf PATH gefunden“

Das Werkzeug des Schritts ist nicht installiert. Der Schritt trägt im Graph und in der Blockansicht die Markierung „Tool fehlt“, das Schrittpanel zeigt den Hinweis. Das Werkzeug installieren; hat das Modul einen Installationsbefehl, steht er in der Meldung („Installation: …“). Sonst die Schreibweise des Werkzeugs prüfen.

### „Arbeitsverzeichnis … existiert nicht“

Mit `--cwd` einen vorhandenen Ordner angeben.

### Ein Schritt schlägt fehl, obwohl er „richtig“ lief

Manche Werkzeuge liefern Exit-Codes ungleich 0 bei normalem Verhalten, z. B. `grep` Exit 1 bei „keine Treffer“. Im Schritt „Erfolgs-Exitcodes“ auf `0, 1` setzen.

### Der Plan hat sich seit der Bestätigung geändert

Der Plan weicht von dem zuvor bestätigten ab. Den neuen Plan prüfen und erneut bestätigen.

### Workflow mit Terminal-Schritt lässt sich mit `wts run` nicht starten

Terminal-Schritte laufen nur in der Oberfläche (Exit-Code 3). `--dry-run` ist möglich. Ausführen über `wts gui`.

## Terminal-Schritte

| Meldung | Bedeutung und Lösung |
|---|---|
| „Zu viele Terminals gleichzeitig (Limit erreicht). Beende eins und starte neu.“ | Höchstens 4 gleichzeitige Terminals. Ein anderes beenden |
| „Das Terminal ist schon in einem anderen Tab oder Fenster verbunden.“ | Pro Terminal nur eine Verbindung. Den anderen Tab schließen |
| „Terminal beendet: Zeitlimit oder zu lange ohne Ein- und Ausgabe.“ | Zeitlimit des Schritts erreicht oder 15 Minuten Stille. Neu starten, gegebenenfalls das Zeitlimit des Schritts erhöhen |
| „Terminal beendet: Das Programm gibt Ausgabe zu schnell aus.“ | Das Programm hat dem Terminal zu viele Daten gesendet. Neu starten |
| „Terminal nicht gefunden (Schritt läuft nicht mehr).“ | Der Schritt war schon beendet |
| „Terminal-Verbindung beendet (Code N). Ursache siehe Meldungen des Schritts.“ | Meldungen im Ausgabebereich lesen |
| „Kein Terminal verbunden“ | Der Browser hat sich nicht binnen 600 Sekunden verbunden. Exit-Code 124 |
| Der Schritt endet ohne Terminal, Exit-Code 126 | Die Sandbox fehlt (siehe oben) |

Ein beendetes Terminal lässt sich nicht wieder verbinden; ein Neuladen der Seite beendet das Programm.

Transkripte liegen in `~/.cache/whattheshell/terminal/`. Anzeigen und Löschen: `wts terminal transcripts` und `wts terminal transcripts --delete NAME.txt`.

## Module

### Modul wird nicht erkannt

- Dateiname muss auf `.module.yaml`, `.module.yml` oder `.module.json` enden.
- Die Datei muss in einem der Suchordner liegen: `~/.config/whattheshell/modules/` oder `<Projekt>/.whattheshell/modules/` (letzteres nur, wenn `wts` im Projektordner gestartet wurde). `wts modules` zeigt Suchpfade und geladene Module.
- Eine fehlerhafte Datei wird mit Pfad, Zeile und Feldpfad gemeldet und nur sie ist deaktiviert: `wts validate DATEI`. Im Modus „Module“ stehen Fehler unter „Fehler“.
- Eine Datei über 1 MiB wird abgelehnt, ebenso YAML-Aliase und -Anker.
- Eine Datei mit Fehler im Editor: „YAML-Syntaxfehler: …“. Im Rohtext korrigieren.
- `tool` muss dem Namen des Programms auf dem `PATH` entsprechen (ohne Pfad, ohne führendes `-`).
- Ein Projektmodul wird nur geladen, wenn `wts` im Projektordner gestartet wurde.
- Ein eigenes Modul überdeckt ein mitgeliefertes mit demselben Werkzeug. Fehlt der Effekt, `wts inspect TOOL` zeigt das zusammengeführte Ergebnis.
- Beim Zusammenführen die ids aus `wts inspect TOOL --json` verwenden; eine unbekannte id legt eine neue Option an, statt die vorhandene zu ändern.

### Mitgeliefertes Modul anpassen

Das Modul unter demselben Werkzeug als eigenes speichern; es überdeckt dann das mitgelieferte. „Löschen“ entfernt nur eigene Module.

### Modul-Beispiel schlägt fehl

`wts example TOOL` führt die Beispiele in der Sandbox aus und zeigt, welche Erwartung (`expect`) nicht zutrifft. Ohne Sandbox werden sie übersprungen.

## KI-Funktionen

Zuerst `wts ai check` ausführen. Jede Zeile nennt Befund und Hinweis.

| Befund | Lösung |
|---|---|
| „KI aus“ / „KI-Funktionen sind ausgeschaltet.“ | In den Einstellungen aktivieren oder `wts ai enable` |
| Modell nicht eingetragen („kein Modell gesetzt“) | In den Einstellungen eintragen, oder `wts ai config set local.model NAME` bzw. `api.model NAME` |
| Endpunkt nicht erreichbar (lokal) | Modellserver starten, z. B. `ollama serve`; Adresse in den Einstellungen prüfen |
| Modell nicht vorhanden | Modell laden, z. B. `ollama pull NAME`; Namen prüfen |
| Schlüssel fehlt („Schlüsselstatus: fehlt“) | Die in „Umgebungsvariable des Schlüssels“ genannte Variable setzen und den Server **neu starten**: vor `wts gui start` exportieren |
| Cloud-API nicht erreichbar | Netz, Proxy und Endpunkt prüfen |
| Agentenprogramm „nicht im PATH“ / „nicht installiert“ | Programm installieren (`claude` bzw. `codex`); `wts ai check` nennt den Befehl |
| „nicht angemeldet“ | `claude login` bzw. `codex login`. Liegen die Anmeldedaten nur in einem Schlüsselbund, den Schlüssel stattdessen als Umgebungsvariable setzen (z. B. `ANTHROPIC_API_KEY`) |
| „Anmeldedatei nicht kopierbar“ | Rechte der Anmeldedatei im Home-Ordner prüfen |
| „KI beschäftigt. Später erneut versuchen.“ | Es laufen schon zwei Anfragen. Warten |
| „Anbieterfehler“ | Die Meldung des Anbieters lesen; Zeitlimit in den Einstellungen erhöhen, wenn es an der Dauer liegt |
| „Gültig: nein“ in der Antwort | Der Vorschlag ist keine gültige Datei. Verwerfen oder im Editor korrigieren; es wird nichts gespeichert |

Ein Schlüssel gehört nie in die Einstellungsdatei. Werte, die wie ein Schlüssel aussehen, werden dort abgelehnt.

## Einstellungen

### „Einstellungsdatei korrigieren oder löschen“

Die Datei `~/.config/whattheshell/settings.yaml` ist ungültig. Korrigieren oder löschen; die KI-Funktionen sind dann wieder aus (Standard).

## Weiteres

### Die Oberfläche zeigt nur eine Fehlermeldung, die API läuft

Das Paket enthält die Oberfläche nicht (Installation aus einem Quellordner ohne gebaute Oberfläche). Das Programm aus dem Wheel oder von PyPI mit `pipx` installieren.

### Einstellungen der Oberfläche zurücksetzen

Die Websitedaten des Browsers für `127.0.0.1` löschen. Das setzt Sprache, Schriftgröße, Darstellung, Startansicht, Favoriten, Spaltenbreiten und gemerkte Werte zurück. Dateien (Module, Workflows) bleiben unberührt.

### Alles zurücksetzen

```
wts gui stop
rm -r ~/.config/whattheshell ~/.cache/whattheshell
```

Das löscht auch eigene Module und Workflows. Vorher sichern (Kapitel „Dateien und Orte“).
