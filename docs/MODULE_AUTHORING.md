# Modulautorenhandbuch

## 1. Zweck

Ein Modul ist eine YAML-Datei (`*.module.yaml`, auch `.yml`/`.json`), die die Auto-Erkennung eines Befehls ergänzt (`override_mode: merge`) oder ganz ersetzt (`replace`): bessere Labels, Gruppen, Beispiele, Sicherheitsklassen. Es gilt zusammen mit `schemas/module.schema.json`; unbekannte Felder sind Fehler.
Suchpfade, aufsteigende Priorität: mitgeliefert (`whattheshell/bundled/modules/`) → Nutzer `~/.config/whattheshell/modules/` → projektlokal `./.whattheshell/modules/`. Spätere gewinnen.

```bash
mkdir -p ~/.config/whattheshell/modules
wts scaffold grep --user   # Gerüst mit allen erkannten ids nach ~/.config/whattheshell/modules/grep.module.yaml (Ordner wird angelegt)
wts scaffold grep --out pfad/grep.module.yaml   # oder in eine andere Datei; --force überschreibt
$EDITOR ~/.config/whattheshell/modules/grep.module.yaml
wts validate ~/.config/whattheshell/modules/grep.module.yaml
wts inspect grep          # zeigt das zusammengeführte Ergebnis
wts modules --watch       # lädt bei Dateiänderung live neu
```

## 2. Schnellstart

Minimal (nur `schema_version` und `tool` sind Pflicht):

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

Gut (grep-nah):

```yaml
schema_version: 1
tool: grep
display_name: "grep – Text durchsuchen"
category: Text
summary: "Durchsucht Dateien oder Eingaben nach Mustern."
description: |
  Gibt alle Zeilen aus, die zu einem Muster passen.
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
    help: "Unterscheidet nicht zwischen Groß- und Kleinbuchstaben."
  - id: recursive
    flags: ["-r", "--recursive"]
    label: Verzeichnisse rekursiv durchsuchen
    group: Dateien
    importance: common
  - id: context                    # Langform --context -> context; immer per wts inspect prüfen
    flags: ["-C", "--context"]
    label: Kontextzeilen
    type: int
    min: 0
    metavar: NUM
    group: Ausgabe
    importance: normal
output:
  stdout: { kind: lines }
  exit_codes: { 0: "Treffer gefunden", 1: "Keine Treffer", 2: "Fehler" }
examples:
  - title: "Fehlerzeilen finden"
    description: "Sucht error ohne Rücksicht auf Groß-/Kleinschreibung."
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
      ignore_case: { label: "Ignore case", help: "Treats upper and lower case alike." }
    inputs:
      pattern: { label: "Pattern" }
```

Eingabe-ids dürfen frei benannt werden (siehe Abschnitt 4). Bei `merge` immer die Option-id aus `wts inspect grep --json` nehmen; eine unbekannte id hängt eine zusätzliche Option an.

## 3. Felder-Referenz

Pflicht "ja" heißt: Datei ist sonst ungültig. Alle anderen Felder dürfen fehlen.

**Kopf (Modul)**

| Feld | Pflicht | Typ | Bedeutung | Beispiel |
|---|---|---|---|---|
| `schema_version` | ja | `1` | Formatversion | `1` |
| `tool` | ja | string | Name auf PATH; kein Pfad, kein führendes `-` (`^[A-Za-z0-9][A-Za-z0-9._+-]*$`) | `grep` |
| `override_mode` | nein | `merge`/`replace` | Standard `merge` | `replace` |
| `display_name`, `category`, `summary`, `description` | nein | string | Anzeigetexte | `category: Text` |
| `safety` | nein | `safe`/`caution`/`dangerous` | Klasse des Befehls (Abschnitt 5) | `caution` |

**`inputs` (Positionsargumente) und `options`** (gleiche Felder; `flags` nur bei Optionen, `position` nur bei Inputs)

| Feld | Pflicht | Typ | Bedeutung | Beispiel |
|---|---|---|---|---|
| `id` | ja | `^[a-z][a-z0-9_]*$` | Eindeutig über inputs+options; aus `wts inspect TOOL --json`, nicht erfinden. id aus der Langform: `--ignore-case` → `ignore_case`, `--context` → `context`; nur Optionen ohne Langform nutzen die Kurzform (`-C` allein → `c_upper`). Bei Kollision mit einer Option erhält die Eingabe-id das Suffix `_arg` (find: `path_arg`) | `ignore_case` |
| `flags` | nein | Liste string | Nur Optionen | `["-i", "--ignore-case"]` |
| `label` | nein | string | Kurzer Feldname, deutsch | `Kontextzeilen` |
| `type` | nein | `string` `int` `float` `bool` `path` `enum` `secret` | Standard: Option `bool`, Input `string`. Listen über `multiple`, nicht `path[]`. `secret`: kein `default` | `int` |
| `multiple` | nein | bool | Mehrfach erlaubt | `true` |
| `required` | nein | bool | Pflichtfeld | `true` |
| `default` | nein | beliebig | Vorgabewert | `3` |
| `choices` | nein | Liste string | Bei `enum` | `[always, never, auto]` |
| `min`, `max` | nein | Zahl | Bei `int`/`float` | `min: 0` |
| `metavar` | nein | string | Platzhalter aus der Hilfe | `NUM` |
| `group` | nein | string | GUI-Gruppe, deutsch | `Ausgabe` |
| `importance` | nein | `common`/`normal`/`rare` | Reihenfolge/Einklappen; Standard `normal` | `common` |
| `help` | nein | string | Ein Satz, was es bewirkt | `"Zählt statt auszugeben."` |
| `safety` | nein | Safety | Hebt die Klasse an, nie Pflicht | `dangerous` |
| `confidence` | nein | `high`/`medium`/`low` | Standard `high`; nicht setzen | |
| `position` | nein | int | Reihenfolge der Inputs | `0` |

**`output`**: `stdout.kind` (`lines` `text` `json` `csv` `bytes`, Standard `lines`), `exit_codes` (Zahl → Text, z. B. `1: "Keine Treffer"`).

**`subcommands`**: Liste; je Eintrag `name` (Pflicht, eindeutig) plus dieselben Felder wie das Modul ohne `schema_version`, `tool`, `override_mode`, `templates`; rekursiv.
```yaml
subcommands:
  - name: commit
    summary: "Änderungen festhalten"
    options: [ { id: message, flags: ["-m", "--message"], type: string, required: true, label: Nachricht } ]
```

**`examples`**: `title` (Pflicht), `description`, `fixtures` (`path` relativ ohne `..`, `content`), `args` (id → Wert), `expect` (`exit_code`, `stdout_contains`, `stderr_contains`, `stdout_regex`, alle optional, Regex muss kompilieren).

**`templates`**: `title`, `workflow` (Pfad relativ zur Moduldatei, ohne `..`): `{ title: "Treffer zählen", workflow: grep_count.workflow.yaml }`.

**`i18n`**: Sprachcode → `display_name`, `summary`, `description`, `options: {id: {label, help}}`, `inputs: {id: {label, help}}`. Basistexte sind deutsch, `en` ist die Standardübersetzung.

## 4. Merge-Regeln

- `merge` (Standard): Nur im Modul **gesetzte** Felder überschreiben die Auto-Erkennung. Nicht gesetzt = Katalogwert bleibt.
- `options` werden nach `id` zusammengeführt: bekannte id → angegebene Felder überschreiben, unbekannte id → wird angehängt. `inputs` im Modul **ersetzen** die Katalog-Eingaben vollständig: alle Positionsargumente auflisten, frei benennen; die Listenreihenfolge ist die Argumentreihenfolge. `subcommands` nach `name`. `examples`, `templates`, `i18n` werden ergänzt.
- `replace`: Katalogdaten werden verworfen, das Modul ist allein maßgeblich. Nur sinnvoll, wenn die Auto-Erkennung für das Tool unbrauchbar ist.
- Reihenfolge: Katalog → mitgeliefert → Nutzer → projektlokal. Eine fehlerhafte Datei deaktiviert nur sich selbst.
- Für Verfeinerungen reicht `merge` mit wenigen Feldern (`id`, `label`, `group`, `importance`).

## 5. Sicherheitsklassen

Maßgeblich ist das schlimmste, was der Aufruf anrichten kann. Automatische Vorschau läuft nur bei `safe`; `caution` und `dangerous` verlangen Bestätigung.

| Klasse | Wann | Beispiele |
|---|---|---|
| `safe` | Liest nur, schreibt nichts außerhalb von stdout | `grep`, `ls`, `wc`, `sort`, `jq` |
| `caution` | Schreibt/ändert Dateien, begrenzt oder umkehrbar | `cp`, `mv`, `tar -x`, `chmod`, `curl -o datei` |
| `dangerous` | Löscht, überschreibt unumkehrbar, wirkt auf Geräte/System/Rechte | `rm`, `dd`, `mkfs`, `sudo`, `chmod -R`, `sed -i`, `find -delete`, `rsync --delete` |

Auf der **Option** anheben, wenn das Tool sonst harmlos ist:
```yaml
tool: sed
safety: safe
options:
  - { id: in_place, flags: ["-i", "--in-place"], label: Datei direkt ändern, safety: dangerous }
---
tool: find
safety: safe
options:
  - { id: delete, flags: ["-delete"], label: Treffer löschen, safety: dangerous }
---
tool: curl
safety: safe
options:
  - { id: output, flags: ["-o", "--output"], type: path, label: In Datei speichern, safety: caution }
```
(`---` trennt hier nur Beispiele; jedes Modul ist eine eigene Datei.) Befehle, die immer löschen (`rm`, `dd`), bekommen `safety: dangerous` im Kopf. Im Zweifel die höhere Klasse.

## 6. Beispiele und Fixtures

- Beispiele laufen in einer `bwrap`-Sandbox: temporäres Arbeitsverzeichnis, sonst schreibgeschützt, **kein Netz**.
- Nur relative Pfade, keine `..`; `fixtures` legen Dateien im Arbeitsverzeichnis an. Nichts außerhalb anfassen (kein `/etc`, kein `~`).
- Klein (wenige Zeilen) und deterministisch: keine Uhrzeit, Zufallswerte, Hostnamen, sortierabhängige Ausgaben ohne `sort`.
- Ab Phase 3 werden Beispiele automatisch in der Sandbox ausgeführt und müssen dann bestehen.
- `expect` muss zutreffen; sonst gilt das Beispiel als defekt. `stdout_contains` für robuste Prüfung, `stdout_regex` nur bei Bedarf.
- Keine Beispiele mit Netzwerk (`curl http://…`) und keine `caution`/`dangerous`-Beispiele, die Fixtures zerstören sollen.
- `args`: Schlüssel = `id`. `bool` → `true`, Wert-Optionen → Wert, `multiple` → Liste, Inputs wie Optionen:

```yaml
args: { recursive: true, context: 2, pattern: "error", files: ["a.log", "b.log"] }
# entspricht: grep -r -C 2 error a.log b.log
```

## 7. Validierung und Fehlermeldungen

```bash
wts validate grep.module.yaml
```
Gültige Datei:
```
OK: src/whattheshell/bundled/modules/grep.module.yaml (Modul grep)
1 Dateien geprüft, 0 fehlerhaft
```
Fehler (Exit-Code 1), Format `pfad:zeile:` dann `feldpfad: meldung (Eingabe: …)`:
```
a.module.yaml:5:
options[0].lable: Extra inputs are not permitted (Eingabe: 'x')
b.module.yaml:5:
options[0].required: Input should be a valid boolean, unable to interpret input (Eingabe: 'ja')
c.module.yaml:
$: Value error, inputs/options-id 'count' kommt mehrfach vor (Eingabe: {'schema_version': 1, ...)
```
Die drei häufigsten Fehler:
1. **Unbekanntes Feld** (`Extra inputs are not permitted`) (Tippfehler, erfundenes Feld wie `required_if`): Feldpfad lesen, Namen mit Abschnitt 3 abgleichen; Modelle sind strikt.
2. **Falscher Typ/Wert** (`required: "ja"`, `type: integer`, `importance: high`): die Meldung nennt Feldpfad und Problem; erlaubte Enum-Werte stehen in Abschnitt 3; Enums siehe Abschnitt 3.
3. **Doppelte id** (`kommt mehrfach vor`, Feldpfad `$`; inputs und options teilen sich den Namensraum, auch `subcommands[].name`): eine umbenennen, aber die id muss zur Katalog-id passen, sonst entsteht eine neue Option.
Weitere typische Fehler: `fixtures[].path` absolut oder mit `..`; `default` bei `type: secret`; unkompilierbares `stdout_regex`; id mit Großbuchstaben oder Bindestrich.

## 8. Prompt-Vorlage für KI-Agenten

````text
Rolle: Du schreibst ein WhatTheShell-Modul für den Befehl TOOL.

Eingaben:
1. Ausgabe von `wts inspect TOOL --json` (erkannte Optionen mit ids).
2. docs/MODULE_AUTHORING.md (Format, Regeln).
3. schemas/module.schema.json (verbindliche Struktur).

Ausgabe: genau eine YAML-Datei TOOL.module.yaml, nichts anderes (kein Text davor oder danach, keine Erklärungen).

Qualitätsregeln:
- schema_version: 1, tool: TOOL, override_mode: merge.
- Alle Texte (display_name, summary, label, help, group) auf Deutsch, kurz und für Einsteiger verständlich; i18n.en mit englischen Texten.
- ids ausschließlich aus der inspect-Ausgabe; keine erfundenen ids oder Felder.
- Optionen in sinnvolle Gruppen (group) ordnen; 5-8 Optionen mit importance: common, seltene mit rare.
- 2-3 Beispiele mit fixtures, args (Schlüssel = ids) und expect; klein, deterministisch, relative Pfade, kein Netzwerk, nichts außerhalb des Arbeitsordners.
- output.exit_codes befüllen, wenn die Man-Page Exit-Codes nennt.
- safety: Befehl und Optionen nach Abschnitt 5 einstufen; löschende oder überschreibende Optionen anheben.
- Keine type: secret mit default.

Abschlussprüfung: Speichere die Datei und führe `wts validate TOOL.module.yaml` aus. Behebe alle Fehler und wiederhole, bis die Prüfung ohne Fehler endet.
````

Die CLI-Zeile für den Agenten:
```bash
wts validate ~/.config/whattheshell/modules/TOOL.module.yaml && wts inspect TOOL
```

## 9. Checkliste vor dem Teilen

1. `wts validate` meldet keine Fehler und keine Warnungen.
2. Alle ids stammen aus `wts inspect TOOL --json`; keine erfundenen Optionen.
3. `summary`, `label` und `help` sind deutsch, kurz und ohne Tippfehler; `i18n.en` ist vorhanden.
4. Optionen haben `group`; 5-8 sind `common`, seltene `rare`.
5. `safety` ist gesetzt und für löschende, überschreibende oder systemnahe Optionen angehoben.
6. Jedes Beispiel läuft in der Sandbox und `expect` trifft zu; keine Netz- oder Außenpfad-Zugriffe.
7. Keine Geheimnisse, Nutzernamen oder absoluten Pfade in Beispielen, `default` oder `description`.
8. `wts inspect TOOL` zeigt das erwartete Ergebnis, und `override_mode: replace` ist nur gesetzt, wenn es wirklich nötig ist.
