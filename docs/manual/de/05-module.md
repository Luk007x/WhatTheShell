# Module

## Was ein Modul ist

Ein Modul ist eine YAML-Datei (`*.module.yaml`, auch `.yml` oder `.json`), die ein Werkzeug beschreibt: deutsche Beschriftungen, Gruppen, Hilfetexte, Beispiele, Sicherheitsklasse und mehr. Ohne Modul kommt alles aus der Hilfe des Werkzeugs (`--help`); der Klassifizierer rät dann die Sicherheitsklasse, und manche Optionen sind als „geraten“ markiert. Ein Modul ergänzt oder ersetzt diese Auto-Erkennung.

Der Katalog zeigt nur installierte Werkzeuge: Mitgelieferte Module für nicht installierte Werkzeuge erscheinen erst nach der Installation. Das Feld `install` eines Moduls nennt die Installationsbefehle, die bei einem fehlenden Werkzeug angezeigt werden.

Module werden beim Laden nie ausgeführt. Die Beispiele eines Moduls laufen nur in der Sandbox.

### Wo Module liegen

Mehrere Orte, aufsteigend nach Priorität; spätere gewinnen:

| Quelle | Ort | Änderbar |
|---|---|---|
| mitgeliefert | im Programmpaket | nein |
| eigene | `~/.config/whattheshell/modules/` | ja |
| Projekt | `<Projekt>/.whattheshell/modules/` (nur wenn `wts` in diesem Ordner gestartet wird) | von Hand |

Projektmodule werden automatisch geladen; es gibt keine Rückfrage. Nur Module aus Quellen vertrauen, die man kennt.

Eine fehlerhafte Datei deaktiviert nur sich selbst; der Fehler wird mit Pfad, Zeile und Feldpfad gemeldet. Dateien über 1 MiB, YAML-Aliase/-Anker und extrem tiefe Verschachtelung werden abgelehnt.

Mitgeliefert sind Module für `curl`, `find`, `grep`, `jq`, `ls`, `nmcli`, `rsync`, `sed`, `sort`, `tar` und `wc`.

### Zusammenführen (`override_mode`)

- `merge` (Standard): Nur die im Modul gesetzten Felder überschreiben die Auto-Erkennung. Optionen werden nach `id` zusammengeführt: bekannte id überschreibt Felder, unbekannte id hängt eine Option an. Positionsargumente (`inputs`) ersetzen die erkannten vollständig, sobald das Modul welche angibt. Beispiele, Vorlagen und Übersetzungen werden ergänzt.
- `replace`: Die Auto-Erkennung wird verworfen; das Modul ist allein maßgeblich. Nur sinnvoll, wenn die Auto-Erkennung unbrauchbar ist.

## Modus „Module“

Der Modus zeigt links die Suchpfade (mit Anzahl der Module oder „nicht vorhanden“), die Liste der Module mit Herkunft („mitgeliefert“, „eigene“, „Projekt“) und gegebenenfalls Fehler. Ein Klick auf ein Modul öffnet den „Modul-Editor“.

Oben stehen:

| Element | Wirkung |
|---|---|
| Feld „Tool“ und „Neu aus Tool“ | Erzeugt ein Gerüst aus der erkannten Hilfe eines Werkzeugs (wie `wts scaffold`). Gibt es für ein Werkzeug kein Modul, sagt der Editor: „Für TOOL gibt es kein Modul. „Neu aus Tool“ erzeugt ein Gerüst.“ |
| Importieren | Lädt eine `.yaml`/`.yml`-Datei in den Editor. Sie wird erst mit „Speichern“ übernommen |
| Exportieren | Lädt das Modul als `TOOL.module.yaml` herunter |

### Formular und Rohtext

Der Editor hat zwei Reiter:

- **Formular:** Ändert die bekannten Felder. Kommentare in der Datei gehen beim Speichern über das Formular verloren („Kommentare gehen beim Formular-Speichern verloren.“).
- **Rohtext:** Der YAML-Text. Er ist die Quelle der Wahrheit; das Formular ändert nur bekannte Felder. Beispiele lassen sich nur im Rohtext bearbeiten.

YAML-Fehler erscheinen als „YAML-Syntaxfehler: …“. Ungültige Dateien werden beim Speichern mit Pfad und Zeile abgelehnt.

Kopfangaben: „Anzeigename“, „Kategorie“, „Kurzbeschreibung“, „Beschreibung“ und die „Sicherheit“ des Werkzeugs.

Tabellen für „Eingaben“ (Positionsargumente) und „Optionen“ mit diesen Spalten:

| Spalte | Bedeutung |
|---|---|
| id | Kennung, Kleinbuchstaben, Ziffern, `_`; eindeutig |
| Schalter | Die Flags der Option, z. B. `-i`, `--ignore-case` |
| Beschriftung | Kurzer Name im Formular |
| Hilfe | Ein Satz, was die Option bewirkt |
| Gruppe | Überschrift im Formular, z. B. „Suche“ |
| Wichtigkeit | `common` = immer sichtbar, `normal`, `rare` = unter „Selten“ |
| Sicherheit | `safe`, `caution`, `dangerous` |
| Typ | `string`, `int`, `float`, `bool`, `path`, `enum`, `secret` |
| Pflicht | Pflichtfeld |

„Beispiele“ zeigt die Titel der Beispiele (Bearbeiten im Rohtext).

Knöpfe: „Speichern“, „Löschen“ (nur eigene Module), „Zurücksetzen“, „Exportieren“. Bei eingeschalteter KI zusätzlich „Mit KI verbessern“ und „Beispiele mit KI erzeugen“.

Mitgelieferte Module sind nicht änderbar. Wer eines anpassen will, speichert es als eigenes Modul; die eigene Datei überdeckt die mitgelieferte. „Löschen“ entfernt nur die eigene Datei.

### Sicherheitsklassen in Modulen

Maßgeblich ist das Schlimmste, was ein Aufruf anrichten kann.

| Klasse | Wann | Beispiele |
|---|---|---|
| `safe` | Liest nur, schreibt nichts außerhalb der Standardausgabe | `grep`, `ls`, `wc`, `sort`, `jq` |
| `caution` | Schreibt oder ändert Dateien, begrenzt oder umkehrbar | `cp`, `mv`, `tar -x`, `chmod`, `curl -o datei` |
| `dangerous` | Löscht, überschreibt unumkehrbar, wirkt auf Geräte, System oder Rechte | `rm`, `dd`, `mkfs`, `sudo`, `sed -i`, `find -delete`, `rsync --delete` |

Ist ein Werkzeug sonst harmlos, hebt man die Klasse an der **Option** an:

```yaml
tool: sed
safety: safe
options:
  - { id: in_place, flags: ["-i", "--in-place"], label: Datei direkt ändern, safety: dangerous }
```

Ein Modul kann Klassen nur anheben. Die fest eingebauten Listen gefährlicher Werkzeuge (`rm`, `dd`, `sudo` …) lassen sich durch ein Modul nicht absenken.

## Wann der Klassifizierer rät

Ohne Modul stuft das Programm Befehle nach Namen und Optionen ein (z. B. `rm`, `sudo`, `find -delete`, `sed -i`, `--delete`). Unbekannte Werkzeuge bleiben „sicher“. Die Einstufung erkennt weder ein Werkzeug unter anderem Namen noch Gefahr, die erst in einem Wert steckt (z. B. `dd of=/dev/sda`). Für Werkzeuge, bei denen es auf Optionen oder Werte ankommt, lohnt sich daher ein eigenes Modul mit `safety`.

## Auf der Kommandozeile

```
wts modules                  # geladene Module und Suchpfade
wts modules --watch          # bei Dateiänderung live neu laden
wts tools --search grep      # Werkzeuge auf dem PATH finden
wts inspect grep             # erkannte Optionen, Typen, Hilfetexte, Konfidenz (Module eingerechnet)
wts inspect grep --json      # dasselbe als JSON (zeigt die ids)
wts scaffold grep --user     # Gerüst nach ~/.config/whattheshell/modules/grep.module.yaml
wts scaffold grep --out pfad/grep.module.yaml
wts scaffold git commit      # Gerüst für einen Unterbefehl
wts validate DATEI           # Modul oder Workflow prüfen
wts example grep             # Beispiele des Moduls in der Sandbox ausführen
```

`wts scaffold TOOL` ohne Ziel schreibt auf die Standardausgabe; `--out` schreibt in eine Datei (Ordner werden angelegt), `--user` in den Modulordner des Benutzers, `--force` überschreibt. `wts example TOOL [N]` führt ein Beispiel (1-basiert) oder alle aus.

### Ein eigenes Modul anlegen

```
wts scaffold grep --user
$EDITOR ~/.config/whattheshell/modules/grep.module.yaml
wts validate ~/.config/whattheshell/modules/grep.module.yaml
wts inspect grep
```

Das Gerüst enthält alle erkannten ids. Beim Zusammenführen immer die ids aus `wts inspect grep --json` verwenden; eine unbekannte id hängt eine zusätzliche Option an.

Minimales Beispiel (nur `schema_version` und `tool` sind Pflicht):

```yaml
schema_version: 1
tool: grep
summary: "Durchsucht Dateien nach Mustern."
safety: safe
options:
  - id: ignore_case
    label: Groß-/Kleinschreibung ignorieren
    importance: common
```

Ausführlicher:

```yaml
schema_version: 1
tool: grep
display_name: "grep – Text durchsuchen"
category: Text
summary: "Durchsucht Dateien oder Eingaben nach Mustern."
override_mode: merge
safety: safe
inputs:
  - { id: pattern, label: Suchmuster, type: string, required: true, position: 0,
      help: "Regulärer Ausdruck oder fester Text." }
  - { id: files, label: Dateien, type: path, multiple: true, position: 1 }
options:
  - id: ignore_case
    flags: ["-i", "--ignore-case"]
    label: Groß-/Kleinschreibung ignorieren
    group: Suche
    importance: common
  - id: context
    flags: ["-C", "--context"]
    label: Kontextzeilen
    type: int
    min: 0
    metavar: NUM
    group: Ausgabe
output:
  stdout: { kind: lines }
  exit_codes: { 0: "Treffer gefunden", 1: "Keine Treffer", 2: "Fehler" }
examples:
  - title: "Fehlerzeilen finden"
    fixtures:
      - path: app.log
        content: |
          INFO start
          ERROR disk full
          error timeout
    args: { ignore_case: true, pattern: "error", files: ["app.log"] }
    expect: { exit_code: 0, stdout_contains: "disk full" }
i18n:
  en:
    summary: "Searches files or input for patterns."
    options:
      ignore_case: { label: "Ignore case" }
```

### Beispiele in Modulen

Beispiele laufen in der Sandbox mit temporärem Arbeitsordner, sonst schreibgeschützt und ohne Netz. `fixtures` legen Dateien an (nur relative Pfade, kein `..`). `args` verwendet die ids als Schlüssel; `expect` prüft `exit_code`, `stdout_contains`, `stderr_contains` oder `stdout_regex`. Beispiele sollen klein und deterministisch sein, ohne Netzwerk.

### Typische Prüffehler

`wts validate` meldet Fehler im Format `pfad:zeile:` gefolgt von `feldpfad: meldung`:

- Unbekanntes Feld („Extra inputs are not permitted“): Tippfehler oder erfundenes Feld; Modelle sind strikt.
- Falscher Typ oder Wert, z. B. `required: "ja"`: erlaubte Werte stehen oben in den Tabellen.
- Doppelte id („kommt mehrfach vor“): `inputs`, `options` und `subcommands[].name` teilen sich den Namensraum.
- Weitere: `fixtures[].path` absolut oder mit `..`; `default` bei `type: secret`; unkompilierbares `stdout_regex`; id mit Großbuchstaben oder Bindestrich.

Beispiel einer gültigen Prüfung:

```
OK: ~/.config/whattheshell/modules/grep.module.yaml (Modul grep)
1 Dateien geprüft, 0 fehlerhaft
```
