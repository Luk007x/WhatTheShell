# Workflow bauen

Ein Workflow ist eine Folge von Schritten. Kontrollbausteine (Bedingung, Schleife) enthalten eigene Teilfolgen. Die Kanten im Graph werden aus dieser Struktur abgeleitet, nicht gespeichert; deshalb zeigen Graph und Blöcke immer denselben Workflow.

## Schritt anlegen

- **Ziehen:** Ein Werkzeug aus dem Katalog oder einen Kontrollbaustein auf die Arbeitsfläche ziehen. Der Schritt entsteht an der Drop-Stelle.
- **Tastatur:** Im Katalog ein Werkzeug wählen und Strg+Eingabe drücken. Es wird am gewählten Ziel angehängt.
- **Werkzeugleiste:** „Hinzufügen: NAME“ fügt das gewählte Werkzeug ein. Das Feld „Ziel“ bestimmt die Stelle: „ans Ende“, „in Dann“, „in Sonst“ oder „in Schleife“.
- **Block-Ansicht:** Das „+“ am Ende jeder Folge fügt einen Kontrollbaustein oder das gewählte Werkzeug genau dort ein.

Werkzeuge, die als interaktiv erkannt sind (Badge „Terminal“), werden als Terminal-Schritt angelegt. Die Checkbox „Als Terminal-Schritt ausführen“ im Formular schaltet das um.

Jeder Schritt hat eine eindeutige **Schritt-id** (Kleinbuchstaben, Ziffern und `_`, beginnt mit einem Buchstaben; `var` und `item` sind reserviert). Mit „Umbenennen“ ändert man sie. Die id ist der Name in Vorlagen, z. B. `{{ id.stdout }}`. Zusätzlich gibt es eine freie „Beschriftung“.

## Felder eines Befehlsschritts

Schritt anklicken, rechts erscheint das Formular. Pflichtfelder sind mit `*` markiert. Felder, die der Hilfe-Parser nur geraten hat, tragen das Etikett „geraten“; ein Modul kann sie korrigieren.

| Bereich | Bedeutung |
|---|---|
| Unterbefehl | Bei Werkzeugen mit Unterbefehlen (z. B. `nmcli connection modify`) |
| Eingaben | Positionsargumente des Werkzeugs |
| Optionen | Die erkannten Optionen, nach Gruppen geordnet. Mit „Optionen durchsuchen“ filtern. Seltene Optionen stehen unter „Selten“, „Mehr“ klappt weitere auf |
| Freie Argumente | Eine Zeile je Argument; wird unverändert an den Befehl angehängt. Für alles, was das Formular nicht kennt |
| Standardeingabe | „keine“, „Pipe von Schritt“ (stdout eines früheren Schritts), „Text“ oder „Datei“ |
| Arbeitsordner | Ordner, in dem der Befehl läuft (Pfad relativ zum Arbeitsordner des Laufs) |
| Erfolgs-Exitcodes (kommagetrennt) | Exitcodes, die als Erfolg gelten. Standard 0. Beispiel: bei `grep` `0, 1`, weil 1 „keine Treffer“ bedeutet |
| Zeitlimit (Sekunden) | Bricht den Schritt nach dieser Zeit ab |
| Bei Fehler | „abbrechen“ (Standard), „weitermachen“, „wiederholen“ (mit „Anzahl Wiederholungen“) oder „Ersatzschritte“ |

Felder, deren Inhalt eine Vorlage `{{ … }}` enthält, werden nicht auf den Typ geprüft („Enthält eine Vorlage: keine Typprüfung.“).

Werte werden dem Programm immer als einzelne Argumente übergeben, nie als Shell-Zeile. Ein Wert, der mit `-` beginnt, kann vom Werkzeug als Option gelesen werden; das Programm fügt kein `--` ein.

Zusätzlich möglich in der YAML-Datei: `env` (zusätzliche Umgebungsvariablen; bestimmte Namen wie `PATH`, `LD_*` oder `PYTHONPATH` werden mit Warnung verworfen). Ein Schritt mit `env` gilt mindestens als „Vorsicht“.

## Datenfluss

Schritte laufen nacheinander, nie gleichzeitig.

### Ablaufkante und Datenkante

| Kante | Darstellung | Bedeutung |
|---|---|---|
| Ablaufkante | durchgezogen mit Pfeil | Legt die Reihenfolge fest. Vom unteren Anschluss „weiter“ zum oberen Eingang „Ablauf“ des nächsten Schritts |
| Datenkante (Pipe) | gestrichelt, „stdout → stdin“ | Gibt die Ausgabe eines früheren Befehls als Text an die Standardeingabe des nächsten Befehls, wie eine Pipe (senkrechter Strich) in der Shell, nur nacheinander |

Anschlüsse am Knoten:

| Anschluss | Lage | Schrittarten | Bedeutung |
|---|---|---|---|
| Ablauf | oben | alle | Eingang der Reihenfolge |
| weiter | unten Mitte | alle | nächster Schritt derselben Folge |
| dann / sonst | unten links/rechts | Bedingung | erster Schritt der Teilfolge |
| Rumpf | unten links | Schleife | läuft je Zeile der Quelle |
| bei Fehler | unten rechts | Befehl mit „Ersatzschritte“ | Ersatzschritte |
| stdin / stdout | links / rechts | nur Befehl | Datenkante |

Nicht passende Verbindungen werden abgelehnt; die Statuszeile nennt den Grund. Eine Pipe geht nur vorwärts: „stdin kann nur die Ausgabe eines früheren Schritts lesen“. Entf löscht Knoten oder Pipe-Kanten. Terminal-Schritte haben keine stdin/stdout-Anschlüsse.

Eine Pipe lässt sich auch im Formular setzen: „Standardeingabe“ → „Pipe von Schritt“.

### Vorlagen

In (fast) jedes Textfeld eines Schritts lassen sich Werte aus früheren Schritten und Variablen einsetzen:

| Vorlage | Wert |
|---|---|
| `{{ schritt.stdout }}` | Standardausgabe des Schritts mit der id `schritt` |
| `{{ schritt.stderr }}` | Fehlerausgabe |
| `{{ schritt.exit_code }}` | Exitcode |
| `{{ schritt.lines }}` | Ausgabe als Zeilen |
| `{{ var.name }}` | Wert der Variable `name` |
| `{{ item }}` | Aktuelles Element in einer Schleife (oder der Name aus „Name des Elements“) |

Es sind nur diese Formen erlaubt (Name oder Name.Attribut mit `stdout`, `stderr`, `exit_code`, `lines`). Es gibt keine Ausdrücke, Aufrufe oder Filter. Eingesetzte Werte werden nur als Text verwendet, nie ausgewertet. Die Vorlage darf nur auf einen früheren Schritt in derselben oder einer umschließenden Folge zeigen.

Ein buchstäbliches `{{` (z. B. in `docker --format '{{.Names}}'`) schreibt man als `\{{`.

Bei einem Terminal-Schritt sind `stdout` und `stderr` leer; `exit_code` ist gesetzt.

## Variablen

Variablen erscheinen im Detailbereich, wenn kein Schritt gewählt ist. Sie werden beim Start des Workflows abgefragt, außer einer Abfrage-Schritt setzt sie (siehe „Abfrage“). Zugriff im Workflow als `{{ var.name }}`.

| Feld | Bedeutung |
|---|---|
| Name | Muster wie bei Schritt-ids: Kleinbuchstaben, Ziffern, `_` |
| Typ | `string` (Text), `int`, `float`, `bool`, `path`, `enum`, `secret` |
| Pflicht | Beim Start muss ein Wert angegeben werden (nicht bei Variablen, die ein Abfrage-Schritt setzt) |
| Standardwert | Vorbelegung. Bei `secret` nicht erlaubt |
| Beschriftung | Anzeigename im Startformular |
| Hilfetext | Erklärung zum Feld |
| Auswahl | Nur bei `enum`: erlaubte Werte, mit Komma getrennt |
| Muster (Regex) | Nur bei `string` und `path`: Der ganze Wert muss dem regulären Ausdruck entsprechen (höchstens 500 Zeichen) |
| min / max | Nur bei `int` und `float` (in der YAML-Datei) |

Typen im Startformular: Text, Zahl, Auswahl (`enum`), Checkbox (`bool`), Passwortfeld (`secret`), Pfad. Werte vom Typ `secret` werden in Ausgabe und Protokollen als `***` maskiert und nie gemerkt.

„Variable hinzufügen“ legt eine neue an, „Variable entfernen“ löscht sie. Eine mit „Variable setzen“ gesetzte Variable muss hier deklariert sein.

## Kontrollbausteine

### Bedingung (`if`)

Verzweigt in „dann“ und optional „sonst“. Eine Bedingung hat eine **Quelle** und genau **einen Operator**.

Quelle: `schritt.stdout`, `schritt.stderr`, `schritt.exit_code`, `var.name`, `item` oder `file:PFAD`.

| Operator (Anzeige) | Schlüssel | Wert |
|---|---|---|
| ist gleich | `eq` | Text, Zahl oder ja/nein |
| ist ungleich | `ne` | Text, Zahl oder ja/nein |
| enthält | `contains` | Text |
| passt auf Regex | `regex` | regulärer Ausdruck |
| ist leer | `is_empty` | ja/nein (Checkbox „ja“) |
| Zeilenzahl größer | `line_count_gt` | ganze Zahl |
| Zeilenzahl gleich | `line_count_eq` | ganze Zahl |
| Zahl größer | `number_gt` | Zahl |
| Zahl kleiner | `number_lt` | Zahl |
| Zahl gleich | `number_eq` | Zahl |
| JSON-Pfad | `json_path` | Pfad wie `a.b[0]` |
| Datei existiert | `file_exists` | ja/nein (Checkbox „ja“) |

```yaml
- id: pruefe
  kind: if
  condition: { source: zaehle.stdout, number_gt: 0 }
  then:
    - { id: bericht, kind: message, text: "Treffer gefunden." }
  else:
    - { id: ok, kind: message, text: "Alles in Ordnung." }
```

Kombinationen mehrerer Operatoren (und/oder/nicht) gibt es nicht.

### Schleife (`foreach`)

Wiederholt den „Rumpf“ je Zeile der Quelle. Quelle ist z. B. `finde.stdout`. „Name des Elements“ (Standard `item`) benennt die aktuelle Zeile; sie steht im Rumpf als `{{ item }}` bzw. unter dem gewählten Namen zur Verfügung. Bei verschachtelten Schleifen bleiben die Namen der äußeren sichtbar; `item` meint die innerste.

```yaml
- id: je_datei
  kind: foreach
  source: finde.stdout
  as: datei
  body:
    - { id: groesse, tool: wc, args: { bytes: true, files: ["{{ datei }}"] } }
```

### Variable setzen (`set`)

Setzt oder überschreibt eine deklarierte Variable. Felder: „Variable“ und „Wert“ (darf eine Vorlage sein, z. B. `{{ suche.stdout }}`).

### Warten (`wait`)

Verzögert den Lauf um „Sekunden“.

### Meldung (`message`)

Zeigt den „Text“ in der Ausgabe. Vorlagen sind erlaubt.

### Abfrage (`ask`)

Hält den Lauf an und fragt den Benutzer. Die Abfrage zeigt einen **Titel** und einen **Text** (der Text darf Vorlagen enthalten) und fragt die unter `fields` genannten Variablen ab. Diese müssen im Workflow deklariert sein; sie werden wie die Startwerte geprüft (Typ, Pflicht, Auswahl, Grenzen, Muster). Bei einer ungültigen Antwort wird erneut gefragt, die Fehlermeldung steht im Dialog, und bereits Eingetipptes bleibt stehen (Secrets nie).

**Abgefragte Variablen:** Jede Variable, die in `fields` oder `button_variable` einer Abfrage vorkommt, wird nicht beim Start verlangt. Auch eine Pflichtvariable ohne Wert blockiert den Start nicht; die Pflicht wird erst in der Abfrage geprüft. Das Startformular blendet solche Variablen aus und zeigt stattdessen „N Variablen werden im Lauf abgefragt.“

In den Details des Schritts heißen die Felder:

| Feld (YAML) | Bezeichnung im Editor | Bedeutung |
|---|---|---|
| `title` | „Titel“ | Überschrift der Abfrage; leer: „Abfrage“ |
| `text` | „Text“ | Erklärungstext; Vorlagen wie `{{ var.name }}` sind erlaubt |
| `fields` | „Abzufragende Variablen“ | Namen der Variablen, die abgefragt werden; Reihenfolge wie bei den Variablen. Sind noch keine angelegt, steht dort „Variablen zuerst unter „Variablen“ anlegen.“ |
| `buttons` | „Knöpfe“ | Kommagetrennt, mindestens 1, höchstens 6, je höchstens 40 Zeichen, keine Doppelten. Standard: „OK“. Der erste ist der Standard (Enter) |
| `button_variable` | „Knopf-Variable“ | Variable, die die Beschriftung des gedrückten Knopfs erhält („keine“ = nicht speichern). Muss vom Typ `string` oder `enum` sein (bei `enum` muss jeder Knopf eine erlaubte Auswahl sein) und darf nicht zugleich in `fields` stehen |
| `timeout` | „Zeitlimit (Sekunden)“ | Größer als 0. Leer: wartet unbegrenzt. Nach Ablauf endet der Lauf |

Neben den Knöpfen steht in der Oberfläche immer „Lauf abbrechen“. Esc schließt den Dialog nicht, damit der Lauf nicht versehentlich endet. Mit Zeitlimit zeigt der Dialog „Antwort bis in N s“.

„Lauf abbrechen“ in der Abfrage beendet den Lauf mit Status „abgebrochen“ (Exit-Code 2 bei `wts run`). Dasselbe gilt, wenn das `timeout` abläuft („Keine Antwort innerhalb von N s“). Bei `wts run` auf der Kommandozeile wird im Terminal gefragt (siehe Kapitel „Ausführen“).

```yaml
variables:
  ziel: { type: string, required: true, label: "Zielordner" }
  antwort: { type: enum, choices: ["Ja", "Nein"] }
steps:
  - id: frage
    kind: ask
    title: "Sichern?"
    text: "Soll nach {{ var.ziel }} gesichert werden?"
    fields: [ziel]
    buttons: ["Ja", "Nein"]
    button_variable: antwort
    timeout: 120
  - id: pruefe
    kind: if
    condition: { source: var.antwort, eq: "Nein" }
    then:
      - { id: stopp, kind: abort, text: "Nicht gesichert.", exit_code: 1 }
```

### Abbrechen (`abort`)

Beendet den Workflow. Felder: „Text“ (Meldung) und „Exitcode“ (Standard 1).

## Speichern und Dateien

Die Kopfzeile bietet im Modus „Erstellen“:

| Knopf | Wirkung |
|---|---|
| Neu | Leerer Workflow (fragt bei ungespeicherten Änderungen nach) |
| Öffnen | Bibliothek mit Suche, Quellenfilter und Herkunftsmarken „mitgeliefert“, „eigene“, „Projekt“ |
| Speichern (Strg+S) | Schreibt den Workflow |
| Speichern unter | Fragt nach dem „Dateiname (id)“. Die id wird aus dem Namen vorgeschlagen: Kleinbuchstaben, Ziffern, `-` und `_`; beginnt mit Buchstabe oder Ziffer |
| Löschen | Löscht eine eigene Datei |

- **Wohin:** In `~/.config/whattheshell/workflows/ID.workflow.yaml`. Der Workflow erscheint sofort im Modus „Ausführen“.
- Existiert die id schon, wird nachgefragt („existiert schon. Überschreiben?“).
- **Mitgelieferte** und **Projekt**-Workflows lassen sich nicht überschreiben oder löschen. Speichert man einen mitgelieferten Workflow unter derselben id, überdeckt die eigene Datei die mitgelieferte. Liegt eine Projektdatei mit derselben id vor, gewinnt sie, und die Datei ist „Projektdatei, hier nicht änderbar“.
- **Projekt-Workflows** liegen in `.whattheshell/workflows/` im Ordner, in dem `wts` gestartet wurde.
- Kaputte Dateien erscheinen ausgegraut mit `Pfad:Zeile: Meldung`.

Die Position der Knoten im Graph wird in der Datei unter `layout` gespeichert.

### Bibliothek: Filter, Import und Integrität

- **Filter „Quelle“:** Alle, Eigene, Mitgeliefert, Projekt. Jeder Eintrag trägt eine Marke für die Quelle und, wo nötig, eine für die Integrität.
- **Import:** Der Knopf „Importieren“ oder das Hineinziehen einer YAML-Datei in die Bibliothek („YAML-Datei hierher ziehen, um sie zu importieren.“) prüft die Datei und legt sie als eigenen Workflow ab. Vorgeschlagen wird der Dateiname `name.workflow.yaml` („Dateiname“: muss auf `.workflow.yaml` enden, höchstens 1 MiB). Ist die Datei ungültig, werden die Fehler aufgelistet und nichts gespeichert. Gibt es den Namen schon, wird nachgefragt („… existiert schon. Überschreiben?“). Hat eine Projektdatei diesen Namen, gewinnt sie, und der Import wird abgelehnt („Eine Projektdatei mit diesem Namen hat Vorrang. Anderen Namen wählen.“); dann einen anderen Namen wählen.
- **Integrität:** Zu jedem Ordner mit eigenen und Projekt-Workflows führt die App eine Stempeldatei `.wts-integrity.json` mit einer Prüfsumme je Workflow. Speichern, Importieren, KI-Freigabe und „Prüfen und übernehmen“ aktualisieren den Stempel. Status einer Datei:

| Status (Marke) | Bedeutung |
|---|---|
| ok (keine Marke) | Die Datei passt zum Stempel. Mitgelieferte Workflows sind immer ok. |
| Außerhalb geändert | Die Datei wurde außerhalb der App geändert (z. B. im Texteditor). |
| Nicht geprüft | Es gibt keinen Stempel: Die Datei wurde von Hand abgelegt oder ist eine ältere eigene Datei. Nach dem Update auf diese Version zeigen vorhandene eigene Dateien einmalig „Nicht geprüft“. |
| Ungültig | Die Datei besteht die Prüfung nicht; die Marke nennt den ersten Fehler. |

Workflows mit „Außerhalb geändert“ oder „Nicht geprüft“ laufen erst, wenn Sie sie angesehen und **„Prüfen und übernehmen“** geklickt haben (Meldung: „Datei wurde außerhalb der App geändert. Prüfen und übernehmen.“). Ein Trockenlauf ist immer erlaubt. Auf der Kommandozeile: `wts workflows list` (zeigt Quelle und Status), `wts workflows import DATEI [--overwrite]`, `wts workflows accept ID` und `wts run --accept`. Ein loser Dateipfad bei `wts run` gilt als „Nicht geprüft“ und braucht `--accept`; er bekommt keinen Stempel.

Das ist Änderungserkennung, kein Manipulationsschutz: Wer die Datei ändern darf, kann auch den Stempel ändern. Die Bestätigungen vor einem Lauf bleiben bestehen.

## Vorschau eines Schritts in der Sandbox

Im Formular eines Befehls: Abschnitt „Vorschau“. Optional ein „Beispiel“ wählen (übernimmt die Argumente aus dem Modul; „ohne Beispieldaten“ ist ebenfalls möglich), dann „Beispiel ausführen“. Die Vorschau zeigt „Exitcode“, „Dauer“ und die Ausgabe.

- Läuft immer in der `bwrap`-Sandbox, ohne Netz; Änderungen werden verworfen.
- Eine Vorschau hat 10 Sekunden Zeit und höchstens 1 MiB Ausgabe („Ausgabe gekürzt“, „Zeitlimit erreicht“).
- Ohne Sandbox: „Sandbox nicht verfügbar“; „Erneut testen“ wiederholt den Selbsttest.
- Automatisch läuft die Vorschau nur, wenn die Einstellung „Vorschau automatisch ausführen“ an ist, der Befehl „sicher“ ist und ein Beispiel gewählt ist.

## Beispiel-Workflows

Mitgeliefert werden:

| id | Name | Zweck |
|---|---|---|
| `log_errors` | Fehler in Logs zählen | Sucht `ERROR` in allen Logdateien, zählt Treffer und schreibt bei Treffern `bericht.txt` |
| `wlan-5ghz` | WLAN auf 5 GHz fixieren | Bindet eine NetworkManager-Verbindung an die BSSID des 5-GHz-Zugangspunkts |
| `wlan-5ghz-loesen` | WLAN-5-GHz-Bindung lösen | Gegenstück: entfernt die feste BSSID wieder |
| `appimage-install-fedora` | AppImage installieren (Fedora) | Kopiert eine AppImage in den Zielordner, macht sie ausführbar und legt einen Menüeintrag mit Icon an |
| `appimage-install-mint` | AppImage installieren (Linux Mint) | Wie Fedora, prüft aber `libfuse2` statt `fuse`/`fuse-libs` |

Die AppImage-Workflows installieren nichts über den Paketmanager: Fehlen Voraussetzungen (Fedora: `fuse`, `fuse-libs`; Linux Mint: `libfuse2`), meldet der Workflow den passenden `sudo`-Befehl zum selbst Ausführen und bricht ab. Angegeben werden `appimage` (Datei), `name` (Menüname, auch Dateiname), optional `icon` (PNG oder SVG; leer = Standard-Icon), `categories` und `target_dir` (leer = `Applications` im Home-Verzeichnis). Der Workflow kopiert die Datei dorthin, macht sie ausführbar und schreibt `~/.local/share/applications/NAME.desktop`. Alle Schritte laufen ohne Shell; Kopieren, Rechte und Schreiben verlangen eine Bestätigung. Erscheint der Eintrag nicht sofort im Menü, einmal ab- und anmelden.

Zum Modul `grep` gehört die Vorlage „Treffer zählen“ (`grep_count`). Vorlagen eines Werkzeugs erscheinen unter „Vorlagen“; „Einfügen“ übernimmt sie in den Workflow.

### „WLAN auf 5 GHz fixieren“ erklärt

Der Workflow ist für Fedora mit NetworkManager (`nmcli`) gedacht. Er benötigt zusätzlich das Werkzeug `iw`.

Variablen:

- `ssid` (Pflicht): „Verbindungsname (SSID)“, Name der Verbindung laut `nmcli connection show`.
- `bssid` (Pflicht): BSSID des 5-GHz-Eintrags aus Schritt 1, Format `AA:BB:CC:DD:EE:FF`. Das Muster prüft dieses Format.

Schritte:

1. `scan`: `nmcli device wifi list` mit den Feldern BSSID, Kanal, Frequenz, Signal und SSID.
2. `liste`: Meldung mit der Liste. Einträge ab 5180 MHz sind 5 GHz.
3. `binden`: `nmcli connection modify SSID 802-11-wireless.bssid BSSID` bindet die Verbindung an den Zugangspunkt. Klasse „Vorsicht“, also mit Bestätigung.
4. `aktivieren`: `nmcli connection up SSID`. Schlägt das fehl, zeigt der Ersatzpfad („bei Fehler“) eine Meldung und beendet mit `abort`.
5. `check`: `iw dev` zeigt den aktuellen Kanal.
6. `auswertung`: Eine Bedingung mit Regex sucht eine Kanalangabe im 5-GHz- oder 6-GHz-Bereich. Treffer: „WLAN läuft auf 5 GHz.“ Sonst: Hinweis, die Verbindung neu aufzubauen.

Den Ablauf probiert man am besten zuerst als Trockenlauf aus; die Befehle stehen dann im Plan, ohne dass etwas verändert wird.

Die BSSID muss beim Start eingetragen werden. Sie lässt sich vorab mit demselben Befehl wie in Schritt 1 ermitteln (`nmcli device wifi list`).
