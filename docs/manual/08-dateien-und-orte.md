# Dateien und Orte

## Speicherorte

| Was | Ort |
|---|---|
| Programm (bei Installation mit pipx) | `~/.local/share/pipx/venvs/whattheshell`, Befehl `~/.local/bin/wts` |
| Einstellungen der KI (`settings.yaml`) | `~/.config/whattheshell/settings.yaml` (nur für den Benutzer lesbar) |
| Eigene Module | `~/.config/whattheshell/modules/` |
| Eigene Workflows | `~/.config/whattheshell/workflows/` |
| Projektlokale Module und Workflows | `<Projekt>/.whattheshell/modules/` und `<Projekt>/.whattheshell/workflows/` (nur wenn `wts` in diesem Ordner gestartet wird) |
| Mitgelieferte Module und Workflows | im Programmpaket, nicht änderbar |
| Arbeitsordner der Läufe (Oberfläche, wenn kein Arbeitsordner angegeben ist) | `~/.config/whattheshell/runs/ID` |
| Cache (erkannte Hilfetexte der Werkzeuge) | `~/.cache/whattheshell/` |
| Log des im Hintergrund gestarteten Servers | `~/.cache/whattheshell/gui.log` |
| Terminal-Transkripte | `~/.cache/whattheshell/terminal/` |
| Zustand der laufenden Instanz (`gui.json`, Sperre) | `$XDG_RUNTIME_DIR/whattheshell/` (Fallback `~/.cache/whattheshell/run/`) |
| Menüeintrag | `~/.local/share/applications/whattheshell.desktop` |
| Einstellungen der Oberfläche (Sprache, Schriftgröße, Darstellung, Startansicht, Vorschau-Option, zuletzt eingegebene Werte, Spaltenbreiten, Favoriten) | Lokaler Speicher (`localStorage`) des Browsers für `127.0.0.1` |

`XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_RUNTIME_DIR` und `XDG_DATA_HOME` werden beachtet. Ist eine davon gesetzt, liegen die Ordner dort statt unter `~/.config`, `~/.cache`, `~/.local/share`.

Die Einstellungen der Oberfläche gehören zum Browser: Ein anderer Browser, ein anderes Profil oder das Löschen der Websitedaten setzt sie zurück. Auch ändert sich der lokale Speicher nicht mit den Dateien oben.

### Suchreihenfolge

Module und Workflows werden an drei Orten gesucht, aufsteigend nach Priorität; bei gleicher id oder gleichem Werkzeug gewinnt der spätere:

1. mitgeliefert (im Paket),
2. eigene (`~/.config/whattheshell/…`),
3. Projekt (`./.whattheshell/…` im Startordner von `wts`).

In der Bibliothek erscheint nur der Gewinner; „überdeckt: …“ nennt die verdeckten Quellen. Der Server beobachtet die Ordner, Änderungen erscheinen ohne Neustart.

Dateinamen:

| Art | Endungen |
|---|---|
| Modul | `*.module.yaml`, `*.module.yml`, `*.module.json` |
| Workflow | `*.workflow.yaml`, `*.workflow.yml`, `*.workflow.json` |

Die id eines Workflows ist der Dateiname ohne Endung.

## Dateiformate

Workflows und Module sind YAML-Dateien (alternativ JSON). Beide tragen `schema_version`:

```yaml
schema_version: 1
```

Ein Dokument muss ein Objekt sein. Unbekannte Felder sind Fehler, damit Tippfehler auffallen.

### Workflow

```yaml
schema_version: 1
name: "Fehler in Logs zählen"
description: "Sucht ERROR in allen Logdateien."
variables:
  logdir: { type: path, default: "./logs", label: "Log-Ordner" }
steps:
  - id: suche
    tool: grep
    args: { patterns: ERROR, recursive: true, files: ["{{ var.logdir }}"] }
    ok_exit_codes: [0, 1]
  - id: pruefe
    kind: if
    condition: { source: suche.stdout, is_empty: false }
    then:
      - { id: treffer, kind: message, text: "Treffer:\n{{ suche.stdout }}" }
    else:
      - { id: ok, kind: message, text: "Alles in Ordnung." }
layout:
  nodes: { suche: { x: 0, y: 0 } }
```

Schrittarten (`kind`):

| `kind` | Pflichtfelder | Bedeutung |
|---|---|---|
| `command` (Standard, wenn `tool` gesetzt ist) | `tool` | Externes Programm; `command` (Unterbefehle), `args`, `extra_args`, `stdin`, `cwd`, `env`, `timeout`, `ok_exit_codes`, `on_error` |
| `terminal` | `tool` | Interaktives Programm; wie `command`, aber ohne `stdin`; dazu `network` |
| `if` | `condition`, `then` | `else` optional |
| `foreach` | `source`, `body` | Je Zeile; `as` benennt das Element |
| `set` | `variable`, `value` | Variable setzen |
| `wait` | `seconds` | Verzögerung |
| `message` | `text` | Meldung |
| `ask` | – | Abfrage: `title`, `text`, `fields`, `buttons`, `button_variable`, `timeout` |
| `abort` | – | Beenden; `text`, `exit_code` |

Regeln für ids: Muster `^[a-z][a-z0-9_]*$`, im ganzen Workflow eindeutig; `var` und `item` sind reserviert. `stdin.pipe` und Vorlagen zeigen nur auf Schritte, die davor liegen. `on_error` kennt `abort`, `continue`, `retry` (mit `retries`) und `fallback` (mit `steps`).

`layout` (Knotenpositionen) ist optional und betrifft nur den Graph.

### Modul

Feldreferenz und Beispiele im Kapitel „Module“.

### Migration

`schema_version` ist Pflicht. Derzeit gibt es nur Version 1.

## Module exportieren und importieren

- **Exportieren:** Im Modus „Module“ das Modul wählen, „Exportieren“ lädt `TOOL.module.yaml` herunter.
- **Importieren:** „Importieren“ lädt eine `.yaml`- oder `.yml`-Datei in den Editor. Erst „Speichern“ legt sie als eigenes Modul in `~/.config/whattheshell/modules/` ab.
- Von Hand: Die Datei in `~/.config/whattheshell/modules/` kopieren (oder für ein Projekt nach `.whattheshell/modules/`) und mit `wts validate DATEI` prüfen.
- Auch Workflows lassen sich als Dateien weitergeben: `~/.config/whattheshell/workflows/ID.workflow.yaml` kopieren.

Fremde Dateien vor dem Gebrauch ansehen und mit „Trockenlauf“ oder `wts run --dry-run` prüfen.

## Prüfen

```
wts validate DATEI [DATEI …]    # Modul oder Workflow prüfen
wts workflows                   # Bibliothek auflisten (Quelle, id, Name, Schritte, Pfad)
wts modules                     # Suchpfade und geladene Module
```

`wts validate` meldet Fehler mit Datei, Zeile und Feldpfad; Exit-Code 1 bei Fehlern.

## Backup

Zu sichern ist:

```
~/.config/whattheshell/modules/
~/.config/whattheshell/workflows/
~/.config/whattheshell/settings.yaml
```

Dazu gegebenenfalls `.whattheshell/` in den eigenen Projekten. Der Cache (`~/.cache/whattheshell/`) lässt sich jederzeit löschen; er wird neu aufgebaut. Der Ordner `~/.config/whattheshell/runs/` enthält die Arbeitsdateien der Läufe in der Oberfläche; er wird nicht automatisch geleert und kann gelöscht werden, wenn die Ergebnisse nicht mehr gebraucht werden.

Eine Datei aus dem Cache wird bei Beschädigung automatisch verworfen und neu erzeugt.
