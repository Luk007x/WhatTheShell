# Installation und Start

## Voraussetzungen

| Voraussetzung | Wofür |
|---|---|
| Linux | Das Programm ist für Linux gebaut. Getestet wird auf Ubuntu und Fedora; es wird nichts Distributionsspezifisches benötigt. |
| Python ab 3.11 | Laufzeit des Programms. |
| `bubblewrap` (`bwrap`) | Sandbox für Vorschau, Modul-Beispiele und Terminal-Schritte. Ohne `bwrap` gibt es keine Vorschau und keine Terminal-Schritte. |
| `util-linux` (`setsid`, `prlimit`) | Wird von der Sandbox und den Terminal-Schritten benötigt. Fehlt `prlimit`, läuft die Sandbox mit Warnung ohne Speicher- und Prozesslimit. |
| Browser | Die Oberfläche läuft im Browser. |

Node.js wird nur zum Bauen der Oberfläche benötigt, nicht zur Laufzeit: Das Paket enthält die fertige Oberfläche.

Die Sandbox braucht unprivilegierte User-Namespaces. Wo diese gesperrt sind (z. B. durch AppArmor oder eine Systemeinstellung), ist die Sandbox nicht verfügbar.

## Installation

```
sudo apt install bubblewrap pipx          # bzw. der Paketmanager der Distribution
pipx install whattheshell
```

Wenn das Paket noch nicht auf PyPI veröffentlicht ist, lässt sich ein Wheel direkt installieren:

```
pipx install ./whattheshell-0.0.1-py3-none-any.whl
```

Danach liegt der Befehl `wts` in `~/.local/bin/wts` (Programm selbst: `~/.local/share/pipx/venvs/whattheshell`).

### Prüfen, ob alles vorhanden ist

```
wts sandbox
```

`wts sandbox` führt einen Selbsttest der Sandbox aus. Fehlt etwas, zeigt die Ausgabe den Installationsbefehl der jeweiligen Distribution. In der Oberfläche zeigt die Kopfzeile „Sandbox bereit“ oder „Sandbox nicht verfügbar“.

## Starten

| Befehl | Wirkung |
|---|---|
| `wts gui start` | Startet den Server im Hintergrund und öffnet den Browser. Läuft schon eine Instanz, wird nur der Browser geöffnet. |
| `wts gui status` | Zeigt Port, PID und Laufzeit. Exit-Code 3 bedeutet: nicht gestartet. |
| `wts gui stop` | Beendet den Server (SIGTERM, nach 15 s SIGKILL). Laufende Workflows werden abgebrochen. |
| `wts gui` | Startet im Vordergrund. Strg+C beendet. Ein zweites `wts gui` startet keinen zweiten Server. |
| `wts gui --port N` | Feste Portnummer statt eines freien Ports. |
| `wts gui --no-browser` | Browser nicht öffnen; die Adresse wird ausgegeben. |
| `wts gui --install-desktop` | Legt den Menüeintrag „WhatTheShell“ an. |

Der Server öffnet den Browser über eine kurze private Weiterleitungsseite. Dadurch steht das Sitzungstoken nicht in der Prozessliste.

### Sprache der Meldungen

Meldungen von Server und Kommandozeile `wts` folgen der gewählten Sprache. Auf der Kommandozeile stellt `wts --lang de` oder `wts --lang en` sie für einen Aufruf ein, die Umgebungsvariable `WTS_LANG` für die Sitzung; ohne beides gilt die Systemsprache, bei anderen Sprachen als Deutsch und Englisch Englisch. Die Sprache der Oberfläche steht in den Einstellungen („Sprache“).

### Menüeintrag

```
wts gui --install-desktop
```

schreibt `~/.local/share/applications/whattheshell.desktop` (bzw. unter `$XDG_DATA_HOME/applications`). Der Eintrag ruft `wts gui start` auf. Er erscheint danach im Anwendungsmenü unter dem Namen „WhatTheShell“.

### Sitzungstoken und `127.0.0.1`

Beim Start erzeugt der Server ein zufälliges Sitzungstoken. Die Adresse sieht so aus:

```
http://127.0.0.1:PORT/#token=…
```

- Der Teil nach `#` geht nie an den Server; die Oberfläche liest ihn im Browser und sendet ihn bei jeder Anfrage mit.
- Ohne Token zeigt die Seite: „Bitte über `wts gui` starten. Die Adresse mit Sitzungstoken (#token=…) fehlt.“
- Das Token gilt nur für diese Sitzung. Nach einem Neustart des Servers gibt es ein neues.
- Der Server bindet ausschließlich an `127.0.0.1`. Er ist aus dem Netzwerk nicht erreichbar. Warum das wichtig ist: Der Server kann Befehle ausführen. Würde eine fremde Webseite oder ein anderer Rechner ihn erreichen, könnte sie Befehle auslösen. Das Token und die Prüfung von Host und Herkunft der Anfragen verhindern das.
- Ein Start als root wird verweigert.

Wer die Adresse mit Token weitergibt oder in den Browserverlauf schaut: Das Token ist nur so lange gültig, wie der Server läuft.

### Beenden

- In der Oberfläche: Einstellungen (Zahnrad), Abschnitt „Programm“, Knopf „WhatTheShell beenden“. Laufende Workflows werden abgebrochen. Danach erscheint die Meldung, dass der Tab geschlossen werden kann.
- Auf der Kommandozeile: `wts gui stop`.
- Das Schließen des Browser-Tabs beendet den Server nicht.

## Aktualisieren

```
wts gui stop
pipx upgrade whattheshell        # bzw. uv tool upgrade whattheshell / pip install -U whattheshell
wts gui start
```

Einstellungen (`~/.config/whattheshell`), eigene Module und eigene Workflows bleiben erhalten, weil sie nicht im Paket liegen. Eine Aktualisierung aus der laufenden Oberfläche heraus gibt es nicht.

## Deinstallieren

```
wts gui stop
pipx uninstall whattheshell
```

`pipx uninstall` lässt alle Daten des Benutzers liegen. Zum vollständigen Entfernen zusätzlich:

```
rm -r ~/.config/whattheshell ~/.cache/whattheshell
rm ~/.local/share/applications/whattheshell.desktop     # falls der Menüeintrag angelegt wurde
```

Damit verschwinden Einstellungen, eigene Module und Workflows, Cache, Hintergrund-Log und Terminal-Transkripte. Vorher gegebenenfalls sichern (Kapitel „Dateien und Orte“). Wurden die Umgebungsvariablen `XDG_CONFIG_HOME` oder `XDG_CACHE_HOME` gesetzt, liegen die Ordner dort statt unter `~/.config` und `~/.cache`.

Die Einstellungen der Oberfläche (Sprache, Darstellung, Startansicht, zuletzt eingegebene Werte) liegen im lokalen Speicher des Browsers (`localStorage`) und lassen sich dort über die Websitedaten für `127.0.0.1` löschen.

## Wo liegt der Zustand der laufenden Instanz

| Datei | Zweck |
|---|---|
| `$XDG_RUNTIME_DIR/whattheshell/gui.json` | PID, Port und Adresse der laufenden Instanz (Fallback: `~/.cache/whattheshell/run/`) |
| `~/.cache/whattheshell/gui.log` | Log des im Hintergrund gestarteten Servers |

`wts gui stop` beendet nur den Prozess, der wirklich zu dieser Datei gehört. Eine wiederverwendete Prozessnummer trifft keinen fremden Prozess.
