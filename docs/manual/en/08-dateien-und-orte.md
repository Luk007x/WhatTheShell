# Files and locations

## Storage locations

| What | Location |
|---|---|
| Program (when installed with pipx) | `~/.local/share/pipx/venvs/whattheshell`, command `~/.local/bin/wts` |
| AI settings (`settings.yaml`) | `~/.config/whattheshell/settings.yaml` (readable only by the user) |
| Own modules | `~/.config/whattheshell/modules/` |
| Own workflows | `~/.config/whattheshell/workflows/` |
| Project-local modules and workflows | `<project>/.whattheshell/modules/` and `<project>/.whattheshell/workflows/` (only if `wts` is started in this folder) |
| Bundled modules and workflows | in the program package, not editable |
| Working folder of runs (interface, when no working directory is given) | `~/.config/whattheshell/runs/ID` |
| Cache (detected help texts of tools) | `~/.cache/whattheshell/` |
| Log of the server started in the background | `~/.cache/whattheshell/gui.log` |
| Terminal transcripts | `~/.cache/whattheshell/terminal/` |
| State of the running instance (`gui.json`, lock) | `$XDG_RUNTIME_DIR/whattheshell/` (fallback `~/.cache/whattheshell/run/`) |
| Menu entry | `~/.local/share/applications/whattheshell.desktop` |
| Interface settings (language, font size, appearance, start view, preview option, last entered values, column widths, favorites) | Local storage (`localStorage`) of the browser for `127.0.0.1` |

`XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_RUNTIME_DIR` and `XDG_DATA_HOME` are respected. If one of them is set, the folders are located there instead of under `~/.config`, `~/.cache`, `~/.local/share`.

The interface settings belong to the browser: a different browser, a different profile or deleting the site data resets them. Also, local storage does not change with the files above.

### Search order

Modules and workflows are searched in three locations, ascending by priority; for the same id or the same tool, the later one wins:

1. bundled (in the package),
2. own (`~/.config/whattheshell/…`),
3. project (`./.whattheshell/…` in the start folder of `wts`).

The library only shows the winner; "overrides: …" names the hidden sources. The server watches the folders, changes appear without a restart.

File names:

| Kind | Extensions |
|---|---|
| Module | `*.module.yaml`, `*.module.yml`, `*.module.json` |
| Workflow | `*.workflow.yaml`, `*.workflow.yml`, `*.workflow.json` |

A workflow's id is the file name without the extension.

## File formats

Workflows and modules are YAML files (alternatively JSON). Both carry `schema_version`:

```yaml
schema_version: 1
```

A document must be an object. Unknown fields are errors, so that typos stand out.

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

Step kinds (`kind`):

| `kind` | Required fields | Meaning |
|---|---|---|
| `command` (default if `tool` is set) | `tool` | External program; `command` (subcommands), `args`, `extra_args`, `stdin`, `cwd`, `env`, `timeout`, `ok_exit_codes`, `on_error` |
| `terminal` | `tool` | Interactive program; like `command`, but without `stdin`; plus `network` |
| `if` | `condition`, `then` | `else` optional |
| `foreach` | `source`, `body` | Per line; `as` names the element |
| `set` | `variable`, `value` | Set a variable |
| `wait` | `seconds` | Delay |
| `message` | `text` | Message |
| `ask` | – | Prompt: `title`, `text`, `fields`, `buttons`, `button_variable`, `timeout` |
| `abort` | – | Terminate; `text`, `exit_code` |

Rules for ids: pattern `^[a-z][a-z0-9_]*$`, unique in the whole workflow; `var` and `item` are reserved. `stdin.pipe` and templates only point to steps that come before. `on_error` knows `abort`, `continue`, `retry` (with `retries`) and `fallback` (with `steps`).

`layout` (node positions) is optional and only affects the graph.

### Module

Field reference and examples in the chapter "Modules".

### Migration

`schema_version` is required. Currently there is only version 1.

## Exporting and importing modules

- **Export:** In "Modules" mode, choose the module; "Export" downloads `TOOL.module.yaml`.
- **Import:** "Import" loads a `.yaml` or `.yml` file into the editor. Only "Save" stores it as your own module in `~/.config/whattheshell/modules/`.
- By hand: copy the file to `~/.config/whattheshell/modules/` (or, for a project, to `.whattheshell/modules/`) and check it with `wts validate FILE`.
- Workflows can also be passed on as files: copy `~/.config/whattheshell/workflows/ID.workflow.yaml`.

Look at foreign files before use and check them with "Dry run" or `wts run --dry-run`.

## Checking

```
wts validate DATEI [DATEI …]    # Modul oder Workflow prüfen
wts workflows                   # Bibliothek auflisten (Quelle, id, Name, Schritte, Pfad)
wts modules                     # Suchpfade und geladene Module
```

`wts validate` reports errors with file, line and field path; exit code 1 on errors.

## Backup

What to back up:

```
~/.config/whattheshell/modules/
~/.config/whattheshell/workflows/
~/.config/whattheshell/settings.yaml
```

Plus, if applicable, `.whattheshell/` in your own projects. The cache (`~/.cache/whattheshell/`) can be deleted at any time; it is rebuilt. The folder `~/.config/whattheshell/runs/` contains the working files of runs in the interface; it is not emptied automatically and can be deleted when the results are no longer needed.

A file from the cache is automatically discarded and recreated if it is damaged.
