# Ausführen

## Modus „Ausführen“

Im Modus „Ausführen“ lassen sich fertige Workflows starten, ohne den Editor.

- **Bibliothek** (links): Alle Workflows, gruppiert nach „mitgeliefert“, „eigene“ und „Projekt“, mit dem Filter „Quelle“ (Alle, Eigene, Mitgeliefert, Projekt), Marken für Quelle und Integrität („Außerhalb geändert“, „Nicht geprüft“, „Ungültig“), einem Knopf „Prüfen und übernehmen“ für Dateien, die vor einem Lauf übernommen werden müssen, einem Knopf „Importieren“ (oder Drag-and-drop), mit Suche („Workflows suchen“), Schrittzahl und Hinweis „überdeckt: …“, wenn eine Datei höherer Priorität dieselbe id hat. „Aktualisieren“ lädt die Liste neu; sie wird auch beim Moduswechsel und bei Fensterfokus neu geladen. Kaputte Dateien sind ausgegraut und zeigen `Pfad:Zeile: Meldung`.
- **Eingaben** (rechts): Ein Feld je Variable, Pflichtfelder mit `*`, Standardwerte vorbelegt, dazu der Arbeitsordner.
- **Letzte Läufe:** Status, Startzeit und Exitcode; ein Klick lädt den Verlauf schreibgeschützt in die Ausgabe.

Die zuletzt eingegebenen Werte eines Workflows werden im Browser gemerkt, Werte vom Typ `secret` nie.

## Startformular

| Variablentyp | Feld |
|---|---|
| `string` | Textfeld (gegebenenfalls mit Hinweis „Muster: …“) |
| `int`, `float` | Zahlfeld, bei Grenzen „MIN bis MAX“ |
| `enum` | Auswahlliste („– bitte wählen –“) |
| `bool` | Checkbox |
| `path` | Textfeld; „Absoluter Pfad oder relativ zum Arbeitsordner.“ |
| `secret` | Passwortfeld |

Fehlermeldungen vor dem Start: „Pflichtfeld“, „Ganze Zahl erwartet“, „Zahl erwartet“, „Wert aus der Liste wählen“, „Mindestens N“, „Höchstens N“, „Passt nicht zum Muster …“.

### Arbeitsordner

Das Feld „Arbeitsordner“ ist optional. Leer wählt der Server einen Ordner `~/.config/whattheshell/runs/ID` (ID = Kennung des Laufs); der Ordner wird angelegt. Alternativ ein absoluter, existierender Pfad. Relative Pfade in Schritten (z. B. der Bericht `bericht.txt` im Beispiel „Fehler in Logs zählen“) beziehen sich auf diesen Ordner.

## Starten und Bestätigen

„Ausführen“ prüft die Eingaben und zeigt den Dialog „Workflow ausführen?“ mit dem Plan (alle Befehle mit Sicherheitsklasse), der „Höchste Sicherheitsklasse“ und dem „Arbeitsordner“. Erst „Workflow ausführen“ startet den Lauf. Ändert sich der Plan zwischen Anzeige und Start, startet nichts; der Dialog zeigt den neuen Plan zur erneuten Bestätigung („Der Plan hat sich seit der Bestätigung geändert …“).

### Sicherheitsklassen und Rückfragen

| Klasse | Anzeige | Verhalten |
|---|---|---|
| safe | sicher | Läuft ohne Rückfrage |
| caution | Vorsicht | Rückfrage vor jedem Schritt mit dem Klartextbefehl |
| dangerous | gefährlich | Rückfrage vor jedem Schritt mit dem Klartextbefehl, roter Bestätigungsknopf |

Die Rückfrage („Schritt bestätigen“) bietet „Ablehnen“ und „Ausführen“. Wird abgelehnt, endet der Lauf als „Abgebrochen“, ohne dass der Befehl gestartet wurde.

Weitere Regeln:

- Die Klasse wird zweimal bestimmt: vor dem Lauf für den Plan und beim Ausführen mit den eingesetzten Werten (Variablen, Schleifenwerte, Ausgaben früherer Schritte). Es gilt die höhere. Ein Wert kann einen Befehl also nicht heimlich gefährlicher machen, ohne dass nachgefragt wird.
- Die Rückfrage gilt je Schritt und in Schleifen je Durchlauf.
- Ein Schritt mit `env`, mit Arbeitsordner außerhalb des Workflow-Ordners oder mit Datei-Standardeingabe außerhalb gilt mindestens als „Vorsicht“. Der Bestätigungstext zeigt dann `env K=V …`, `(in /pfad)` oder `< datei`.
- Ein Terminal-Schritt mit `network: true` gilt mindestens als „Vorsicht“.
- `sudo`, `su`, `doas`, `pkexec` und `chroot` sind immer „gefährlich“. Das Programm stellt nie von sich aus `sudo` voran.
- Jeder Browser-Tab mit gültigem Token kann Rückfragen beantworten (es ist derselbe Benutzer).

Die Einstufung ist eine Heuristik auf Namen und Optionen. Siehe Kapitel „Sicherheit“.

## Trockenlauf

Der „Trockenlauf“ zeigt nur den Plan: alle Befehle mit Sicherheitsklasse. Es wird nichts ausgeführt und kein Prozess gestartet. Terminal-Schritte erscheinen als „interaktiv, wird übersprungen“.

## Während des Laufs

| Knopf | Wirkung |
|---|---|
| Pause / Weiter | Hält den Lauf an und setzt ihn fort |
| Einzelschritt | Führt den nächsten Schritt aus und hält dann an |
| Abbrechen | Beendet den laufenden Prozess samt Unterprozessen |

Status: „Bereit“, „Vorbereitet“, „Läuft“, „Erfolgreich beendet“, „Fehlgeschlagen“, „Abgebrochen“. Je Schritt steht „ok“, „Fehler“ oder „übersprungen“.

Nach dem Ende:

- „Erneut ausführen“ und „Im Editor öffnen“ (fragt bei ungespeicherten Änderungen nach).
- Bei beendeten Schritten: „Als Variable übernehmen“ fügt einen Schritt ein, der die Ausgabe in die Variable `ID_out` schreibt. „Hier auswerten“ fügt eine Bedingung „stdout nicht leer“ ein.

Begrenzungen: Es laufen höchstens vier Läufe gleichzeitig. Die Liste hält höchstens 50 beendete Läufe. Der Verlauf eines Laufs speichert höchstens 10 000 Ereignisse. Die Ausgabe je Schritt wird auf ein Byte-Limit gekürzt. Läufe liegen nur im Speicher des Servers: Nach `wts gui stop` oder dem Beenden der App sind sie weg. Geschrieben wird nur, was die Befehle selbst in den Arbeitsordner schreiben.

## Ausgabe und Secrets

Die Ausgabe erscheint live, getrennt nach stdout und stderr. Werte von Variablen mit dem Typ `secret` werden in Befehlsanzeige, Ausgabe, Meldungen und Ergebnis als `***` ersetzt.

Grenzen der Maskierung:

- Maskiert wird der exakte Wert. Abgewandelte Formen (Base64, URL-kodiert, gekürzt) bleiben sichtbar.
- Ein Secret mit Zeilenumbruch, das verteilt ausgegeben wird, kann der Maskierung entgehen.
- Ein Secret steht zwangsläufig in der Argumentliste des Programms und ist damit für andere Prozesse desselben Benutzers sichtbar (`/proc/PID/cmdline`). Besser über Umgebung oder Standardeingabe übergeben.
- Reale Läufe erben die volle Umgebung des Benutzers; Secrets in Umgebungsvariablen sind für jedes gestartete Programm sichtbar.

## Abfragen im Lauf

Enthält der Workflow einen Schritt „Abfrage“, hält der Lauf an und zeigt Titel, Text, Eingabefelder und bis zu sechs Knöpfe. Der erste Knopf ist der Standard (Enter). „Lauf abbrechen“ steht immer daneben; bei einem Zeitlimit läuft „Antwort bis in N s“ herunter. Ungültige Eingaben werden mit einer Meldung abgewiesen und erneut abgefragt. „Lauf abbrechen“ oder ein abgelaufenes Zeitlimit beendet den Lauf als abgebrochen.

Variablen, die eine Abfrage setzt, fehlen im Startformular. Statt ihrer steht dort „N Variablen werden im Lauf abgefragt.“ Pflicht und Typ werden erst in der Abfrage geprüft. Siehe Kapitel „Workflow bauen“.

## `wts run` auf der Kommandozeile

```
wts run DATEI.workflow.yaml
wts run ID
```

Das Argument ist eine Workflow-Datei oder die id aus `wts workflows`. Existiert eine Datei mit diesem Namen, hat der Pfad Vorrang vor der id.

Eine lose Datei `x.workflow.yaml` als Pfad an `wts run` braucht jetzt `--accept`, weil sie keinen Stempel hat; mit einer id aus der Bibliothek gilt das nur nach einer Änderung außerhalb der App (`wts workflows accept ID`).

| Option | Wirkung |
|---|---|
| `--dry-run` | Nur den Plan zeigen, nichts ausführen |
| `--yes`, `-y` | Alle Bestätigungen mit ja beantworten |
| `--var NAME=WERT` | Variable setzen (mehrfach möglich) |
| `--cwd PFAD` | Arbeitsverzeichnis (Standard: aktuelles Verzeichnis) |
| `--json` | Ergebnis als JSON statt Live-Ausgabe |

Beispiele:

```
wts workflows                                       # Bibliothek auflisten
wts run log_errors --dry-run
wts run log_errors --var logdir=./logs
wts run wlan-5ghz --var ssid=Heimnetz --var bssid=AA:BB:CC:DD:EE:FF
wts run backup.workflow.yaml --yes --json > ergebnis.json
```

Ablauf:

1. Der Workflow wird geladen und geprüft. Nichts wird beim Laden ausgeführt.
2. Die Übersicht (Plan mit Sicherheitsklassen) wird ausgegeben.
3. Enthält der Plan „Vorsicht“ oder „gefährlich“, fragt `wts run` im Terminal „Workflow ausführen? [j/N]“ und danach je Schritt mit dem Klartextbefehl. Mit `--yes` entfällt jede Rückfrage.
4. Ohne Terminal (z. B. in einem Skript) und ohne `--yes` bricht `wts run` bei riskanten Workflows ab: „Bestätigung nötig, aber kein Terminal: mit --yes bestätigen oder --dry-run“.
5. Enthält der Workflow einen Abfrage-Schritt, fragt `wts run` im Terminal (siehe unten). Ohne Terminal bricht es mit „Abfrage-Schritt braucht ein Terminal oder die GUI.“ ab, Exit-Code 3.

`--yes` bestätigt alles ohne Rückfrage, auch gefährliche Schritte. Es ist für Skripte gedacht; vorher mit `--dry-run` prüfen.

### Abfragen im Terminal

- Titel, Text und Fehlermeldungen erscheinen auf stderr. Je Variable wird „Beschriftung (name): “ abgefragt, mit dem bisherigen Wert in `[eckigen Klammern]`. Eine leere Eingabe behält den Standardwert bzw. bisherigen Wert.
- `secret`: verdeckte Eingabe, nichts wird angezeigt.
- `enum`: nummerierte Liste; Nummer oder Wert eingeben, sonst „Ungültige Auswahl. Nummer oder Wert eingeben.“
- `bool`: „[j/n]“, akzeptiert j, ja, n, nein.
- Bei mehreren Knöpfen folgt „Knopf: “ mit nummerierter Liste (Nummer oder Beschriftung); bei einem Knopf entfällt die Frage.
- Ende der Eingabe (Strg+D) in einem Textfeld bricht die Abfrage ab: Exit-Code 2.

### Exit-Codes

| Code | Bedeutung |
|---|---|
| 0 | Workflow erfolgreich beendet |
| 1 | Workflow fehlgeschlagen |
| 2 | Abgebrochen oder abgelehnt, auch fehlende Bestätigung ohne Terminal |
| 3 | Eingabefehler: Datei ungültig, Abfrage-Schritt ohne Terminal, `--var` nicht als `NAME=WERT`, Arbeitsverzeichnis fehlt, Variablenwert ungültig, Workflow mit Terminal-Schritt |

Mit `--cwd` lassen sich Dateien eines Laufs in einem bestimmten Ordner ablegen. Im Unterschied zur Oberfläche läuft `wts run` standardmäßig im aktuellen Verzeichnis, nicht in `~/.config/whattheshell/runs/ID`.

Workflows mit Terminal-Schritten lassen sich nicht mit `wts run` ausführen (Hinweis auf `wts gui`, Exit-Code 3). `--dry-run` funktioniert.

## Terminal-Schritte

Terminal-Schritte führen interaktive Programme wie `vim`, `less`, `top`, `ssh` im Browser aus. Das Terminal erscheint im Laufpanel.

- **Nur in der Oberfläche.** Nicht mit `wts run`.
- **Immer in der Sandbox.** Ohne `bwrap` startet der Schritt nicht; eine Meldung mit Installationshinweis erscheint, Exit-Code 126.
- **Rechte:** Das Programm läuft als normaler Benutzer in der Sandbox: `/home`, `/root`, `/tmp`, `/var/tmp` und `/run` sind leer bzw. verdeckt, das übrige Dateisystem ist nur lesbar. Beschreibbar ist allein der Arbeitsordner des Schritts (in der Sandbox unter `/tmp/work`). Der Arbeitsordner muss innerhalb des Laufordners liegen; andere Pfade werden abgelehnt. `sudo`, `su` und `pkexec` funktionieren nicht.
- **Netz:** Standardmäßig kein Netz. Das Feld „Netzzugang erlauben“ (`network`) erlaubt es; der Schritt gilt dann als „Vorsicht“.
- **Höchstens 4 Terminals gleichzeitig.** Weitere werden abgewiesen: „Zu viele Terminals gleichzeitig (Limit erreicht). Beende eins und starte neu.“
- **Eine Verbindung je Terminal.** Ist das Terminal schon in einem anderen Tab verbunden, erscheint eine Meldung.
- **Zeitlimits:** Das Zeitlimit des Schritts; 15 Minuten ohne Ein- oder Ausgabe beenden das Terminal. Verbindet sich der Browser nicht binnen 600 Sekunden, endet der Schritt mit Exit-Code 124 („Kein Terminal verbunden“).
- **Beenden:** Trennen der Verbindung oder Schließen der Seite beendet das Programm. Es gibt kein Wiederverbinden.
- **Bedienung:** Die Tastatur geht an das Programm, Strg+C beendet es. Esc, dann Tab verlässt das Terminal. Nach dem Ende bleibt der Inhalt schreibgeschützt stehen, bis „Schließen“ gewählt wird; der nächste Terminal-Schritt ersetzt ihn.
- **Ausgabe:** Sie geht nicht an Folgeschritte. `{{ schritt.stdout }}` ist leer; der Exitcode steht in `{{ schritt.exit_code }}`. Wer Text weiterreichen will, schreibt eine Datei in den Arbeitsordner.
- **Zwischenablage und Titel:** Escape-Sequenzen eines Programms für Zwischenablage, Fenstertitel und Hyperlinks werden verworfen.
- **Tastatureingaben** werden nirgends gespeichert.

### Transkript

Im Dialog „Workflow ausführen?“ (nur sichtbar bei Workflows mit Terminal-Schritt) gibt es die Option „Terminal-Ausgabe als Transkript speichern“. Standardmäßig aus.

- Gespeichert wird nur die Ausgabe des Programms, nie die Tastatureingabe. Getippte Zeichen erscheinen jedoch als Echo in der Ausgabe.
- Während des Laufs steht „Ausgabe wird gespeichert“.
- Datei: `~/.cache/whattheshell/terminal/LAUF-SCHRITT.txt` (Ordner nur für den Benutzer lesbar). Nach dem Ende zeigt die Oberfläche den Speicherort („Ausgabe gespeichert unter“) und einen Knopf „Löschen“.
- Secret-Werte werden zeilenweise maskiert, nach bestem Bemühen. Zeichenweise Neuzeichnungen (Cursorsprünge) können eine Maskierung umgehen.

Auf der Kommandozeile:

```
wts terminal transcripts                      # Transkripte auflisten
wts terminal transcripts --delete NAME.txt    # eines löschen
```
