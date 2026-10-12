# Dateiformate: Modul und Workflow (Entwurf zur Abnahme, Phase 0)

Quelle der Wahrheit sind die Pydantic-Modelle in `src/whattheshell/models/`. Die JSON-Schemas in
`schemas/` werden daraus erzeugt (`wts schema export`). Dieses Dokument erklärt die Absicht hinter den Modellen.
Beide Dateien sind YAML (alternativ JSON), tragen `schema_version` und liegen unter `~/.config/whattheshell/{modules,workflows}/`
oder projektlokal unter `.whattheshell/`.

## 1. Gemeinsame Bausteine (`models/common.py`)

| Name | Werte | Zweck |
|---|---|---|
| `ValueType` | `string`, `int`, `float`, `bool`, `path`, `enum`, `secret` | Typ eines Eingabefelds. Listen über `multiple: true`, nicht über `path[]`. `secret` wird in Logs maskiert und darf keinen `default` haben. |
| `Safety` | `safe`, `caution`, `dangerous` | Sicherheitsklasse (Projektauftrag 10.2). |
| `Confidence` | `high`, `medium`, `low` | Wie sicher der Hilfe-Parser bei einer Option war. Modulautoren setzen implizit `high`. |
| `Importance` | `common`, `normal`, `rare` | Sortierung und Einklappen in der GUI (F-9). |
| `OutputKind` | `lines`, `text`, `json`, `csv`, `bytes` | Wie stdout zu interpretieren ist. |

`OptionSpec` und `InputSpec` werden **vom Katalog (Auto-Erkennung) und von Modulen gemeinsam** benutzt.
Nur `id` ist Pflicht. Beim Mergen gelten nur die im Modul tatsächlich gesetzten Felder (`model_fields_set`) als Überschreibung.

```yaml
# OptionSpec
id: ignore_case            # Pflicht, snake_case, eindeutig je Befehl
flags: ["-i", "--ignore-case"]
label: Groß-/Kleinschreibung ignorieren
type: bool                 # ValueType, Standard bool bei Optionen ohne Wert
multiple: false            # Option darf mehrfach vorkommen (-I a -I b)
required: false
default: null
choices: []                # bei type enum
min: null                  # bei int/float
max: null
metavar: null              # FILE, NUM, DIR aus der Hilfe
group: Suche
importance: normal
help: "…"
safety: safe               # Option kann die Klasse des Befehls anheben (z. B. --force)
confidence: high
```

`InputSpec` (Positionsargumente) hat dieselben Felder ohne `flags`, plus `position` (Reihenfolge, optional, sonst Listenreihenfolge).

## 2. Katalog (`models/catalog.py`), nicht vom Nutzer geschrieben

`CommandSpec` beschreibt einen Befehl oder Subbefehl rekursiv: `name` (`["git", "commit"]`), `summary`, `usage`, `inputs`,
`options`, `subcommands`, `raw_help`, `confidence` (gesamt), `safety`, `interactive` (erkannt, dann nicht ausführbar).
`ToolInfo`: `name`, `path`, `version`, `help_hash`, `source` (`module`, `help`, `man`, `fallback`), `command: CommandSpec`.
Cache-Schlüssel: `path + version + help_hash` (F-4).

## 3. Modul (`models/module.py`)

Entspricht Projektauftrag 8.1 mit drei Abweichungen (siehe DECISIONS D-004):
Listen über `multiple: true` statt `path[]`; Subbefehle über ein rekursives `subcommands`-Feld; `inputs`/`options` sind `OptionSpec`/`InputSpec` wie oben.

```yaml
schema_version: 1
tool: grep                  # Pflicht, Name auf PATH
display_name: "grep – Text durchsuchen"
category: Text
summary: "…"
description: |
  …
override_mode: merge        # merge | replace
safety: safe
inputs: [ … InputSpec … ]
options: [ … OptionSpec … ]
output:
  stdout: { kind: lines }
  exit_codes: { 0: "Treffer", 1: "Keine Treffer", 2: "Fehler" }
subcommands:                # gleiche Struktur wie das Modul selbst, ohne schema_version/tool/override_mode
  - name: commit
    summary: "…"
    options: [ … ]
examples:
  - title: "…"
    description: "…"
    fixtures: [ { path: app.log, content: "…" } ]
    args: { ignore_case: true, pattern: error, files: [app.log] }   # Schlüssel = id aus inputs/options
    expect: { exit_code: 0, stdout_contains: "disk full" }         # optional, alle Felder optional
templates:
  - { title: "Treffer zählen", workflow: grep_count.workflow.yaml }  # Pfad relativ zur Moduldatei
i18n:                       # optional, Übersetzungen von label/help/summary je Sprache
  en: { summary: "…", options: { ignore_case: { label: "Ignore case" } } }
```

## 4. Workflow (`models/workflow.py`), überarbeitet nach 8.3

### Grundentscheidung: strukturierter Baum statt freier Graph

Der Workflow ist eine **Folge von Schritten**, in der Kontrollstrukturen (`if`, `foreach`) eigene Teilfolgen enthalten.
Begründung: Die Block-Ansicht (Scratch) kann nur verschachtelte Folgen darstellen, nie beliebige Sprünge. Ein freier
Graph wäre also nicht verlustfrei in Blöcke übersetzbar. Umgekehrt ist jeder strukturierte Baum als Knoten-Graph darstellbar:
Knoten = Schritte, Ablaufkanten = Listenreihenfolge plus Branch-Ports (`then`, `else`, `body`), Datenkanten = `stdin.pipe`
und `{{ id.… }}`-Referenzen. **Kanten werden nicht gespeichert, sondern aus dem Baum abgeleitet.** Beide Ansichten sind damit
per Konstruktion verlustfrei (F-32, F-35). Positionen liegen getrennt in `layout` (F-34).

```yaml
schema_version: 1
name: "Fehler in Logs zählen"
description: "…"
variables:
  logdir: { type: path, default: "./logs", label: "Log-Ordner" }   # Schlüssel folgen dem id-Muster
  anzahl: { type: int }                                            # von `set` gesetzt, muss hier deklariert sein
steps:
  - id: finde                      # Pflicht, eindeutig im gesamten Workflow (auch in Teilfolgen)
    kind: command                  # Standard, darf entfallen wenn `tool` gesetzt ist
    tool: find
    command: []                    # Subbefehl-Pfad, z. B. ["commit"] bei git
    args: { path: "{{ var.logdir }}", name: "*.log", type: f }   # Schlüssel = Option-/Input-id
    extra_args: []                 # rohe Zusatzargumente (Fallback „Freie Argumente", F-6)
    cwd: null
    env: {}                        # nur Ergänzungen, Werte dürfen Templates sein
    timeout: null                  # Sekunden
    ok_exit_codes: [0]             # Exit-Codes, die als Erfolg gelten (grep: [0, 1], weil 1 = keine Treffer)
    on_error: { action: abort }    # abort | continue | retry (retries: n) | fallback (steps: [...])
  - id: suche
    tool: grep
    args: { pattern: ERROR, recursive: true, count: true }
    stdin: { pipe: finde }         # oder { text: "{{ finde.stdout }}" } oder { file: pfad }
  - id: pruefe
    kind: if
    condition: { source: suche.stdout, number_gt: 0 }
    then:
      - { id: bericht, tool: tee, args: { file: bericht.txt }, stdin: { text: "{{ suche.stdout }}" } }
    else:
      - { id: ok, kind: message, text: "Alles in Ordnung." }
  - id: je_datei
    kind: foreach
    source: finde.stdout           # Zeilenweise; `item` ist in der Teilfolge als {{ item }} verfügbar
    as: datei
    body:
      - { id: groesse, tool: wc, args: { bytes: true, files: ["{{ datei }}"] } }
  - { id: merke, kind: set, variable: anzahl, value: "{{ suche.stdout }}" }
  - { id: pause, kind: wait, seconds: 1 }
  - { id: stopp, kind: abort, text: "Abgebrochen.", exit_code: 1 }
layout:                            # optional, nur für den Knoten-Graph
  nodes: { finde: { x: 0, y: 0 }, suche: { x: 240, y: 0 } }
```

### Schrittarten (`kind`, diskriminierte Union)

| kind | Pflichtfelder | Bedeutung |
|---|---|---|
| `command` | `tool` | Externes Programm, argv aus `args` nach Katalog/Modul erzeugt. Pipe über `stdin.pipe`. |
| `if` | `condition`, `then` | `else` optional. |
| `foreach` | `source`, `body` | Iteriert über Zeilen der Quelle. `as` benennt das Element (Standard `item`). |
| `set` | `variable`, `value` | Variable setzen/überschreiben. `variable` muss unter `variables` deklariert sein. |
| `wait` | `seconds` | Verzögerung. |
| `message` | `text` | Meldung an den Nutzer. |
| `abort` | – | Workflow beenden, `text` und `exit_code` optional. |

### Bedingungen (`Condition`, F-18)

`source` ist eine Referenz: `<id>.stdout`, `<id>.stderr`, `<id>.exit_code`, `var.<name>`, `item`, oder `file:<pfad>`.
Genau **ein** Operator pro Bedingung (Validator):
`eq`, `ne`, `contains`, `regex`, `is_empty`, `line_count_gt`, `line_count_eq`, `number_gt`, `number_lt`, `number_eq`,
`json_path` (plus `eq`/`ne` auf das Ergebnis in Phase 3), `file_exists`.
Kombinationen `all: [ … ]`, `any: [ … ]`, `not: …` sind vorgesehen, aber erst in Phase 3 (YAGNI jetzt).

### Templates `{{ … }}` (Phase 3 im Detail, Abschnitt 10.7)

Nur Pfadausdrücke: `var.<name>`, `<id>.stdout|stderr|exit_code|lines`, `item`/`<as>`. Keine Codeausführung.
Phase 0 validiert Syntax (genau diese Formen, höchstens ein Punkt) und dass `<id>` ein sichtbarer früherer Schritt,
`<name>` eine deklarierte Variable und `<as>` ein umschließender `foreach`-Name ist. Geprüft werden alle String-Felder eines Schritts.
Ein literales `{{` (z. B. `docker --format '{{.Names}}'`) wird als `\{{` geschrieben; die Engine entfernt den Backslash.

### Validierungsregeln (Pydantic-Validatoren)

- Alle `id`s eindeutig im gesamten Baum, Muster `^[a-z][a-z0-9_]*$`. `var` und `item` sind reserviert, auch für `foreach.as`. `foreach.as` darf keine id überdecken.
- Ein Dokument muss ein Objekt sein; Listen oder Skalare auf oberster Ebene sind ein Fehler mit Hinweis.
- `tool` (Workflow und Modul) folgt `^[A-Za-z0-9][A-Za-z0-9._+-]*$`: kein führendes `-`, kein Pfad.
- Regex-Felder (`condition.regex`, `expect.stdout_regex`) müssen kompilierbar sein.
- Pfade in Modulen (`fixtures[].path`, `templates[].workflow`) sind relativ, ohne `..`, nicht leer.
- Im Modul sind ids über `inputs` und `options` eindeutig, ebenso `subcommands[].name`.
- `stdin.pipe` und `source`/Template-Referenzen zeigen nur auf Schritte, die **vorher** in derselben oder einer umschließenden Folge liegen.
- `layout.nodes` darf nur bekannte ids enthalten (unbekannte werden mit Warnung verworfen, nicht Fehler).
- Fehlermeldungen tragen Dateipfad, YAML-Zeile (soweit ruamel sie liefert, ab Phase 2), Feldpfad, erwarteten Typ.
- Beim Zurückschreiben werden Aliase (`else`, `as`) verwendet, sodass validieren → schreiben → validieren identisch bleibt (Round-Trip).

## 5. Migration

`schema_version` ist Pflicht. `migrate(doc: dict) -> dict` in `models/migrate.py` hebt ältere Versionen an; aktuell nur Version 1, Funktion ist Platzhalter mit Test.

## 6. Modul-Suche und Merge (Phase 2)

Suchpfade, aufsteigende Priorität: mitgelieferte Module im Paket (`whattheshell/bundled/modules/`) → Nutzer (`~/.config/whattheshell/modules/`) → projektlokal (`./.whattheshell/modules/`). Dateinamen `*.module.yaml`, `*.module.yml`, `*.module.json`. Eine Datei mit Fehler deaktiviert nur sich selbst; der Fehler wird mit Pfad, Zeile und Feldpfad gemeldet (F-23).

Merge-Kette je Tool: Katalog-`CommandSpec` → Modul 1 → Modul 2 … in Prioritätsreihenfolge. Regeln:

- `override_mode: merge` (Standard): nur im Modul **gesetzte** Felder (`model_fields_set`) überschreiben. `options` werden **nach `id`** zusammengeführt: bekannte id → Felder überschreiben, unbekannte id → anhängen. `inputs` (Positionsargumente) **ersetzen** die Katalogliste vollständig, sobald das Modul sie setzt: Autoren listen alle Positionsargumente, dürfen sie frei benennen, und die Reihenfolge der Liste ist die Argumentreihenfolge. `subcommands` rekursiv nach `name`. `examples`, `templates`, `i18n` ergänzen (anhängen bzw. Schlüssel überschreiben). `interactive` wird übernommen, wenn gesetzt.
- `override_mode: replace`: Katalogdaten werden verworfen, das Modul ist allein die Wahrheit (nur `raw_help` bleibt erhalten). Spätere Module in der Kette mergen darauf. `replace` wirkt nur auf der Wurzelebene des Tools; Overrides für Subbefehle (`subcommands[]`) mergen immer.
- Dateien über 1 MiB, YAML-Aliase/-Anker und zu tiefe Verschachtelung werden abgelehnt (Schutz vor YAML-Bomben; Modul-Ordner sind fremder Input).
- Vom Modul gesetzte Optionen bekommen `confidence: high`; Katalogoptionen behalten ihre Konfidenz.
- Das Ergebnis ist ein `CommandSpec` (um `display_name`, `category`, `description`, `output`, `examples`, `templates`, `i18n` erweitert). `ToolInfo.module_files` nennt die angewandten Dateien in Reihenfolge.

Option-ids kommen aus der Langform (`--ignore-case` → `ignore_case`); nur Optionen ohne Langform bekommen eine id aus der Kurzform (`-C` ohne `--context` → `c_upper`). Kollidiert eine Eingabe-id mit einer Option-id (find: Eingabe `path`, Option `-path`), hängt der Parser an die Eingabe `_arg` an. `wts scaffold TOOL` erzeugt das Gerüst mit allen erkannten ids, damit niemand raten muss.
