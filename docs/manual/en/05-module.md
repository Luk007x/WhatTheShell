# Modules

## What a module is

A module is a YAML file (`*.module.yaml`, also `.yml` or `.json`) that describes a tool: labels, groups, help texts, examples, safety class and more. Without a module, everything comes from the tool's help (`--help`); the classifier then guesses the safety class, and some options are marked as "guessed". A module supplements or replaces this auto-detection.

The catalog shows only installed tools: bundled modules for tools that are not installed appear only after installation. A module's `install` field gives the install commands shown when a tool is missing.

Modules are never executed on load. A module's examples only run in the sandbox.

### Where modules live

Several locations, ascending by priority; later ones win:

| Source | Location | Editable |
|---|---|---|
| bundled | in the program package | no |
| own | `~/.config/whattheshell/modules/` | yes |
| project | `<project>/.whattheshell/modules/` (only if `wts` is started in this folder) | by hand |

Project modules are loaded automatically; there is no confirmation. Only trust modules from sources you know.

A faulty file only disables itself; the error is reported with path, line and field path. Files over 1 MiB, YAML aliases/anchors and extremely deep nesting are rejected.

Bundled are modules for `curl`, `find`, `grep`, `jq`, `ls`, `nmcli`, `rsync`, `sed`, `sort`, `tar` and `wc`.

### Merging (`override_mode`)

- `merge` (default): Only the fields set in the module override the auto-detection. Options are merged by `id`: a known id overrides fields, an unknown id appends an option. Positional arguments (`inputs`) completely replace the detected ones as soon as the module specifies any. Examples, templates and translations are added.
- `replace`: The auto-detection is discarded; the module alone is authoritative. Only useful if the auto-detection is unusable.

## "Modules" mode

The mode shows on the left the search paths (with the number of modules or "missing"), the list of modules with origin ("bundled", "own", "project") and, where applicable, errors. A click on a module opens the "Module editor".

At the top are:

| Element | Effect |
|---|---|
| "Tool" field and "New from tool" | Creates a scaffold from the detected help of a tool (like `wts scaffold`). If there is no module for a tool, the editor says: "There is no module for TOOL. “New from tool” creates a scaffold." |
| Import | Loads a `.yaml`/`.yml` file into the editor. It is only adopted with "Save" |
| Export | Downloads the module as `TOOL.module.yaml` |

### Form and raw text

The editor has two tabs:

- **Form:** Changes the known fields. Comments in the file are lost when saving from the form ("Comments are lost when saving from the form.").
- **Raw text:** The YAML text. It is the source of truth; the form only changes known fields. Examples can only be edited in the raw text.

YAML errors appear as "YAML syntax error: …". Invalid files are rejected on saving with path and line.

Header details: "Display name", "Category", "Summary", "Description" and the tool's "Safety".

Tables for "Inputs" (positional arguments) and "Options" with these columns:

| Column | Meaning |
|---|---|
| id | Identifier, lowercase letters, digits, `_`; unique |
| Flags | The option's flags, e.g. `-i`, `--ignore-case` |
| Label | Short name in the form |
| Help | One sentence on what the option does |
| Group | Heading in the form, e.g. "Search" |
| Importance | `common` = always visible, `normal`, `rare` = under "Rare" |
| Safety | `safe`, `caution`, `dangerous` |
| Type | `string`, `int`, `float`, `bool`, `path`, `enum`, `secret` |
| Required | Required field |

"Examples" shows the titles of the examples (edit them in the raw text).

Buttons: "Save", "Delete" (own modules only), "Reset", "Export". With AI switched on, additionally "Improve with AI" and "Generate examples with AI".

Bundled modules cannot be changed. To adapt one, save it as your own module; your own file overrides the bundled one. "Delete" only removes your own file.

### Safety classes in modules

The worst thing a call can do is what counts.

| Class | When | Examples |
|---|---|---|
| `safe` | Only reads, writes nothing outside standard output | `grep`, `ls`, `wc`, `sort`, `jq` |
| `caution` | Writes or changes files, limited or reversible | `cp`, `mv`, `tar -x`, `chmod`, `curl -o datei` |
| `dangerous` | Deletes, overwrites irreversibly, affects devices, system or permissions | `rm`, `dd`, `mkfs`, `sudo`, `sed -i`, `find -delete`, `rsync --delete` |

If a tool is otherwise harmless, raise the class at the **option**:

```yaml
tool: sed
safety: safe
options:
  - { id: in_place, flags: ["-i", "--in-place"], label: Datei direkt ändern, safety: dangerous }
```

A module can only raise classes. The built-in lists of dangerous tools (`rm`, `dd`, `sudo` …) cannot be lowered by a module.

## When the classifier guesses

Without a module, the program classifies commands by names and options (e.g. `rm`, `sudo`, `find -delete`, `sed -i`, `--delete`). Unknown tools stay "safe". The classification recognizes neither a tool under a different name nor danger that only lies in a value (e.g. `dd of=/dev/sda`). For tools where options or values matter, it is therefore worth writing your own module with `safety`.

## On the command line

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

`wts scaffold TOOL` without a target writes to standard output; `--out` writes to a file (folders are created), `--user` to the user's module folder, `--force` overwrites. `wts example TOOL [N]` runs one example (1-based) or all of them.

### Creating your own module

```
wts scaffold grep --user
$EDITOR ~/.config/whattheshell/modules/grep.module.yaml
wts validate ~/.config/whattheshell/modules/grep.module.yaml
wts inspect grep
```

The scaffold contains all detected ids. When merging, always use the ids from `wts inspect grep --json`; an unknown id appends an additional option.

Minimal example (only `schema_version` and `tool` are required):

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

More detailed:

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

### Examples in modules

Examples run in the sandbox with a temporary working folder, otherwise read-only and without network. `fixtures` create files (relative paths only, no `..`). `args` uses the ids as keys; `expect` checks `exit_code`, `stdout_contains`, `stderr_contains` or `stdout_regex`. Examples should be small and deterministic, without network.

### Typical validation errors

`wts validate` reports errors in the format `path:line:` followed by `fieldpath: message`:

- Unknown field ("Extra inputs are not permitted"): typo or invented field; models are strict.
- Wrong type or value, e.g. `required: "ja"`: allowed values are in the tables above.
- Duplicate id ("occurs more than once"): `inputs`, `options` and `subcommands[].name` share the namespace.
- Others: `fixtures[].path` absolute or with `..`; `default` with `type: secret`; uncompilable `stdout_regex`; id with uppercase letters or a hyphen.

Example of a valid check:

```
OK: ~/.config/whattheshell/modules/grep.module.yaml (Modul grep)
1 Dateien geprüft, 0 fehlerhaft
```
