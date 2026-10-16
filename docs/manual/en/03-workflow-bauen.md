# Building a workflow

A workflow is a sequence of steps. Control blocks (condition, loop) contain their own sub-sequences. The edges in the graph are derived from this structure, not stored; that is why graph and blocks always show the same workflow.

## Creating a step

- **Dragging:** Drag a tool from the catalog or a control block onto the canvas. The step is created at the drop position.
- **Keyboard:** Choose a tool in the catalog and press Ctrl+Enter. It is appended at the chosen target.
- **Toolbar:** "Add: NAME" inserts the chosen tool. The "Target" field determines the position: "at the end", "into “Then”", "into “Else”" or "into “Loop”".
- **Blocks view:** The "+" at the end of each sequence inserts a control block or the chosen tool exactly there.

Tools that are detected as interactive (badge "Terminal") are created as a terminal step. The checkbox "Run as terminal step" in the form toggles this.

Every step has a unique **step id** (lowercase letters, digits and `_`, starting with a letter; `var` and `item` are reserved). You change it with "Rename". The id is the name used in templates, e.g. `{{ id.stdout }}`. There is also a free-form "Label".

## Fields of a command step

Click a step and the form appears on the right. Required fields are marked with `*`. Fields that the help parser only guessed carry the tag "guessed"; a module can correct them.

| Area | Meaning |
|---|---|
| Subcommand | For tools with subcommands (e.g. `nmcli connection modify`) |
| Inputs | Positional arguments of the tool |
| Options | The detected options, ordered by group. Filter with "Search options". Rare options are under "Rare", "More" expands further ones |
| Free arguments | One line per argument; appended to the command unchanged. For everything the form does not know |
| Standard input | "none", "Pipe from step" (stdout of an earlier step), "Text" or "File" |
| Working directory | Folder in which the command runs (path relative to the run's working folder) |
| Success exit codes (comma separated) | Exit codes that count as success. Default 0. Example: for `grep` `0, 1`, because 1 means "no matches" |
| Timeout (seconds) | Aborts the step after this time |
| On error | "abort" (default), "continue", "retry" (with "Number of retries") or "fallback steps" |

Fields whose content contains a template `{{ … }}` are not type-checked ("Contains a template: no type check.").

Values are always passed to the program as individual arguments, never as a shell line. A value that starts with `-` may be read by the tool as an option; the program does not insert `--`.

Additionally possible in the YAML file: `env` (extra environment variables; certain names such as `PATH`, `LD_*` or `PYTHONPATH` are discarded with a warning). A step with `env` counts as at least "caution".

## Data flow

Steps run one after another, never at the same time.

### Flow edge and data edge

| Edge | Appearance | Meaning |
|---|---|---|
| Flow edge | solid with arrow | Defines the order. From the lower port "next" to the upper input "flow" of the next step |
| Data edge (pipe) | dashed, "stdout → stdin" | Passes the output of an earlier command as text to the standard input of the next command, like a pipe (vertical bar) in the shell, only sequentially |

Ports on the node:

| Port | Position | Step kinds | Meaning |
|---|---|---|---|
| flow | top | all | Input of the sequence |
| next | bottom center | all | next step of the same sequence |
| then / else | bottom left/right | condition | first step of the sub-sequence |
| body | bottom left | loop | runs per line of the source |
| on error | bottom right | command with "fallback steps" | fallback steps |
| stdin / stdout | left / right | command only | data edge |

Connections that do not fit are rejected; the status line gives the reason. A pipe only goes forward: "stdin can only read the output of an earlier step". Delete removes nodes or pipe edges. Terminal steps have no stdin/stdout ports.

You can also set a pipe in the form: "Standard input" → "Pipe from step".

### Templates

In (almost) every text field of a step you can insert values from earlier steps and variables:

| Template | Value |
|---|---|
| `{{ step.stdout }}` | Standard output of the step with the id `step` |
| `{{ step.stderr }}` | Error output |
| `{{ step.exit_code }}` | Exit code |
| `{{ step.lines }}` | Output as lines |
| `{{ var.name }}` | Value of the variable `name` |
| `{{ item }}` | Current element in a loop (or the name from "Element name") |

Only these forms are allowed (name or name.attribute with `stdout`, `stderr`, `exit_code`, `lines`). There are no expressions, calls or filters. Inserted values are only used as text, never evaluated. The template may only point to an earlier step in the same or an enclosing sequence.

A literal `{{` (e.g. in `docker --format '{{.Names}}'`) is written as `\{{`.

For a terminal step, `stdout` and `stderr` are empty; `exit_code` is set.

## Variables

Variables appear in the details area when no step is selected. They are asked for when the workflow starts, unless a prompt step sets them (see "Prompt"). Access in the workflow as `{{ var.name }}`.

| Field | Meaning |
|---|---|
| Name | Pattern as for step ids: lowercase letters, digits, `_` |
| Type | `string` (text), `int`, `float`, `bool`, `path`, `enum`, `secret` |
| Required | A value must be given at start (not for variables that a prompt step sets) |
| Default | Preset value. Not allowed for `secret` |
| Label | Display name in the start form |
| Help text | Explanation for the field |
| Choices | Only for `enum`: allowed values, separated by commas |
| Pattern (regex) | Only for `string`: the whole value must match the regular expression (at most 500 characters) |
| min / max | Only for `int` and `float` (in the YAML file) |

Types in the start form: text, number, choice (`enum`), checkbox (`bool`), password field (`secret`), path. Values of type `secret` are masked as `***` in output and logs and never remembered.

"Add variable" creates a new one, "Remove variable" deletes it. A variable set with "Set variable" must be declared here.

## Control blocks

### Condition (`if`)

Branches into "then" and optionally "else". A condition has one **source** and exactly **one operator**.

Source: `step.stdout`, `step.stderr`, `step.exit_code`, `var.name`, `item` or `file:PATH`.

| Operator (displayed) | Key | Value |
|---|---|---|
| equals | `eq` | text, number or yes/no |
| does not equal | `ne` | text, number or yes/no |
| contains | `contains` | text |
| matches regex | `regex` | regular expression |
| is empty | `is_empty` | yes/no (checkbox "yes") |
| line count greater | `line_count_gt` | whole number |
| line count equals | `line_count_eq` | whole number |
| number greater | `number_gt` | number |
| number less | `number_lt` | number |
| number equals | `number_eq` | number |
| JSON path | `json_path` | path like `a.b[0]` |
| file exists | `file_exists` | yes/no (checkbox "yes") |

```yaml
- id: pruefe
  kind: if
  condition: { source: zaehle.stdout, number_gt: 0 }
  then:
    - { id: bericht, kind: message, text: "Treffer gefunden." }
  else:
    - { id: ok, kind: message, text: "Alles in Ordnung." }
```

There are no combinations of several operators (and/or/not).

### Loop (`foreach`)

Repeats the "body" per line of the source. The source is e.g. `finde.stdout`. "Element name" (default `item`) names the current line; it is available in the body as `{{ item }}` or under the chosen name. With nested loops, the names of the outer ones stay visible; `item` means the innermost.

```yaml
- id: je_datei
  kind: foreach
  source: finde.stdout
  as: datei
  body:
    - { id: groesse, tool: wc, args: { bytes: true, files: ["{{ datei }}"] } }
```

### Set variable (`set`)

Sets or overwrites a declared variable. Fields: "Variable" and "Value" (may be a template, e.g. `{{ suche.stdout }}`).

### Wait (`wait`)

Delays the run by "Seconds".

### Message (`message`)

Shows the "Text" in the output. Templates are allowed.

### Prompt (`ask`)

Pauses the run and asks the user. The prompt shows a **title** and a **text** (the text may contain templates) and asks for the variables named under `fields`. These must be declared in the workflow; they are checked like the start values (type, required, choices, bounds, pattern). On an invalid answer, the user is asked again, the error message appears in the dialog, and what has already been typed stays (secrets never).

**Prompted variables:** Every variable that appears in `fields` or `button_variable` of a prompt is not required at start. Even a required variable without a value does not block the start; the requirement is only checked in the prompt. The start form hides such variables and shows "N variables are asked for during the run." instead.

In the step's details the fields are named:

| Field (YAML) | Label in the editor | Meaning |
|---|---|---|
| `title` | "Title" | Heading of the prompt; empty: "Prompt" |
| `text` | "Text" | Explanatory text; templates like `{{ var.name }}` are allowed |
| `fields` | "Variables to ask for" | Names of the variables that are asked for; order as in the variables. If none are created yet, it says "Create variables first under “Variables”." |
| `buttons` | "Buttons" | Comma-separated, at least 1, at most 6, each at most 40 characters, no duplicates. Default: "OK". The first is the default (Enter) |
| `button_variable` | "Button variable" | Variable that receives the label of the pressed button ("none" = do not store). Must be of type `string` or `enum` (for `enum`, every button must be an allowed choice) and must not also be in `fields` |
| `timeout` | "Time limit (seconds)" | Greater than 0. Empty: waits without limit. The run ends when it expires |

Next to the buttons, the interface always shows "Cancel run". Esc does not close the dialog, so the run does not end by accident. With a time limit, the dialog shows "Answer within N s".

"Cancel run" in the prompt ends the run with status "Aborted" (exit code 2 for `wts run`). The same applies when the `timeout` expires ("No answer within N s"). With `wts run` on the command line, the question is asked in the terminal (see the chapter "Running").

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

### Abort (`abort`)

Ends the workflow. Fields: "Text" (message) and "Exit code" (default 1).

## Saving and files

In "Build" mode the header offers:

| Button | Effect |
|---|---|
| New | Empty workflow (asks if there are unsaved changes) |
| Open | Library with search and origin tags "bundled", "own", "project" |
| Save (Ctrl+S) | Writes the workflow |
| Save as | Asks for the "File name (id)". The id is suggested from the name: lowercase letters, digits, `-` and `_`; starts with a letter or digit |
| Delete | Deletes an own file |

- **Where to:** `~/.config/whattheshell/workflows/ID.workflow.yaml`. The workflow appears immediately in "Run" mode.
- If the id already exists, you are asked ("already exists. Overwrite?").
- **Bundled** and **project** workflows cannot be overwritten or deleted. If you save a bundled workflow under the same id, your own file overrides the bundled one. If a project file with the same id exists, it wins, and the file is "Project file, not editable here".
- **Project workflows** live in `.whattheshell/workflows/` in the folder where `wts` was started.
- Broken files appear greyed out with `path:line: message`.

The position of the nodes in the graph is saved in the file under `layout`.

## Preview of a step in the sandbox

In a command's form: section "Preview". Optionally choose an "Example" (takes the arguments from the module; "without example data" is also possible), then "Run example". The preview shows "Exit code", "Duration" and the output.

- Always runs in the `bwrap` sandbox, without network; changes are discarded.
- A preview has 10 seconds and at most 1 MiB of output ("output truncated", "timed out").
- Without a sandbox: "Sandbox unavailable"; "Test again" repeats the self-test.
- The preview only runs automatically if the setting "Run preview automatically" is on, the command is "safe" and an example is chosen.

## Example workflows

Bundled:

| id | Name | Purpose |
|---|---|---|
| `log_errors` | Fehler in Logs zählen (Count errors in logs) | Searches for `ERROR` in all log files, counts matches and writes `bericht.txt` if there are any |
| `wlan-5ghz` | WLAN auf 5 GHz fixieren (Pin Wi-Fi to 5 GHz) | Binds a NetworkManager connection to the BSSID of the 5 GHz access point |
| `wlan-5ghz-loesen` | WLAN-5-GHz-Bindung lösen (Release Wi-Fi 5 GHz binding) | Counterpart: removes the fixed BSSID again |

The module `grep` comes with the template "Count matches" (`grep_count`). A tool's templates appear under "Templates"; "Insert" adds them to the workflow.

### "WLAN auf 5 GHz fixieren" (Pin Wi-Fi to 5 GHz) explained

The workflow is intended for Fedora with NetworkManager (`nmcli`). It additionally needs the tool `iw`.

Variables:

- `ssid` (required): "Connection name (SSID)", name of the connection according to `nmcli connection show`.
- `bssid` (required): BSSID of the 5 GHz entry from step 1, format `AA:BB:CC:DD:EE:FF`. The pattern checks this format.

Steps:

1. `scan`: `nmcli device wifi list` with the fields BSSID, channel, frequency, signal and SSID.
2. `liste`: Message with the list. Entries from 5180 MHz upward are 5 GHz.
3. `binden`: `nmcli connection modify SSID 802-11-wireless.bssid BSSID` binds the connection to the access point. Class "caution", so with confirmation.
4. `aktivieren`: `nmcli connection up SSID`. If this fails, the fallback path ("on error") shows a message and ends with `abort`.
5. `check`: `iw dev` shows the current channel.
6. `auswertung`: A condition with a regex looks for a channel entry in the 5 GHz or 6 GHz range. Match: "Wi-Fi is running on 5 GHz." Otherwise: a hint to re-establish the connection.

It is best to try the sequence first as a dry run; the commands then appear in the plan without anything being changed.

The BSSID must be entered at start. You can determine it beforehand with the same command as in step 1 (`nmcli device wifi list`).
