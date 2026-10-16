# Running

## "Run" mode

In "Run" mode you can start finished workflows without the editor.

- **Library** (left): All workflows, grouped by "bundled", "own" and "project", with search ("Search workflows"), step count and the note "overrides: …" when a file of higher priority has the same id. "Refresh" reloads the list; it is also reloaded when you switch modes and on window focus. Broken files are greyed out and show `path:line: message`.
- **Inputs** (right): One field per variable, required fields with `*`, default values preset, plus the working directory.
- **Recent runs:** Status, start time and exit code; a click loads the history read-only into the output.

The values you last entered for a workflow are remembered in the browser, values of type `secret` never.

## Start form

| Variable type | Field |
|---|---|
| `string` | Text field (possibly with the note "Pattern: …") |
| `int`, `float` | Number field, with bounds "MIN to MAX" |
| `enum` | Selection list ("– please choose –") |
| `bool` | Checkbox |
| `path` | Text field; "Absolute path or relative to the working directory." |
| `secret` | Password field |

Error messages before the start: "Required", "Whole number expected", "Number expected", "Pick a value from the list", "At least N", "At most N", "Does not match pattern …".

### Working directory

The "Working directory" field is optional. If empty, the server chooses a folder `~/.config/whattheshell/runs/ID` (ID = identifier of the run); the folder is created. Alternatively an absolute, existing path. Relative paths in steps (e.g. the report `bericht.txt` in the "Fehler in Logs zählen" (Count errors in logs) example) refer to this folder.

## Starting and confirming

"Run" checks the inputs and shows the dialog "Run workflow?" with the plan (all commands with safety class), the "Highest safety class" and the "Working directory". Only "Run workflow" starts the run. If the plan changes between display and start, nothing starts; the dialog shows the new plan for confirmation again ("The plan changed since you confirmed it. …").

### Safety classes and confirmations

| Class | Display | Behavior |
|---|---|---|
| safe | safe | Runs without asking |
| caution | caution | Asks before every step with the plain command |
| dangerous | dangerous | Asks before every step with the plain command, red confirm button |

The confirmation ("Confirm step") offers "Reject" and "Run". If rejected, the run ends as "Aborted" without the command having been started.

Further rules:

- The class is determined twice: before the run for the plan, and at execution time with the substituted values (variables, loop values, outputs of earlier steps). The higher one applies. A value therefore cannot secretly make a command more dangerous without you being asked.
- The confirmation applies per step and, in loops, per iteration.
- A step with `env`, with a working directory outside the workflow folder, or with file standard input from outside counts as at least "caution". The confirmation text then shows `env K=V …`, `(in /path)` or `< file`.
- A terminal step with `network: true` counts as at least "caution".
- `sudo`, `su`, `doas`, `pkexec` and `chroot` are always "dangerous". The program never prepends `sudo` on its own.
- Every browser tab with a valid token can answer confirmations (it is the same user).

The classification is a heuristic based on names and options. See the chapter "Security".

## Dry run

The "Dry run" only shows the plan: all commands with safety class. Nothing is executed and no process is started. Terminal steps appear as "interactive, will be skipped".

## During the run

| Button | Effect |
|---|---|
| Pause / Resume | Pauses the run and continues it |
| Single step | Runs the next step and then pauses |
| Abort | Ends the running process including child processes |

Status: "Ready", "Prepared", "Running", "Finished successfully", "Failed", "Aborted". Per step it says "ok", "failed" or "skipped".

After the end:

- "Run again" and "Open in editor" (asks if there are unsaved changes).
- For finished steps: "Keep as variable" inserts a step that writes the output to the variable `ID_out`. "Evaluate here" inserts a condition "stdout not empty".

Limits: At most four runs execute at the same time. The list keeps at most 50 finished runs. A run's history stores at most 10,000 events. The output per step is truncated to a byte limit. Runs exist only in the server's memory: after `wts gui stop` or quitting the app they are gone. The only things written are what the commands themselves write into the working directory.

## Output and secrets

The output appears live, separated into stdout and stderr. Values of variables of type `secret` are replaced by `***` in the command display, output, messages and result.

Limits of the masking:

- The exact value is masked. Altered forms (Base64, URL-encoded, truncated) remain visible.
- A secret with a line break that is output in pieces can escape the masking.
- A secret necessarily appears in the program's argument list and is therefore visible to other processes of the same user (`/proc/PID/cmdline`). It is better to pass it via the environment or standard input.
- Real runs inherit the user's full environment; secrets in environment variables are visible to every program started.

## Prompts during a run

If the workflow contains a "Prompt" step, the run pauses and shows the title, text, input fields and up to six buttons. The first button is the default (Enter). "Cancel run" is always next to them; with a time limit, "Answer within N s" counts down. Invalid input is rejected with a message and asked for again. "Cancel run" or an expired time limit ends the run as aborted.

Variables that a prompt sets are missing from the start form. Instead it says "N variables are asked for during the run." Required and type are only checked in the prompt. See the chapter "Building a workflow".

## `wts run` on the command line

```
wts run DATEI.workflow.yaml
wts run ID
```

The argument is a workflow file or the id from `wts workflows`. If a file with this name exists, the path takes precedence over the id.

| Option | Effect |
|---|---|
| `--dry-run` | Only show the plan, execute nothing |
| `--yes`, `-y` | Answer all confirmations with yes |
| `--var NAME=VALUE` | Set a variable (can be repeated) |
| `--cwd PATH` | Working directory (default: current directory) |
| `--json` | Result as JSON instead of live output |

Examples:

```
wts workflows                                       # Bibliothek auflisten
wts run log_errors --dry-run
wts run log_errors --var logdir=./logs
wts run wlan-5ghz --var ssid=Heimnetz --var bssid=AA:BB:CC:DD:EE:FF
wts run backup.workflow.yaml --yes --json > ergebnis.json
```

Procedure:

1. The workflow is loaded and checked. Nothing is executed on load.
2. The overview (plan with safety classes) is printed.
3. If the plan contains "caution" or "dangerous", `wts run` asks in the terminal "Run workflow? [y/N]" and then per step with the plain command. With `--yes`, every confirmation is skipped.
4. Without a terminal (e.g. in a script) and without `--yes`, `wts run` aborts for risky workflows: "Confirmation required but no terminal: confirm with --yes or use --dry-run".
5. If the workflow contains a prompt step, `wts run` asks in the terminal (see below). Without a terminal it aborts with "Prompt step needs a terminal or the GUI.", exit code 3.

`--yes` confirms everything without asking, including dangerous steps. It is intended for scripts; check with `--dry-run` first.

### Prompts in the terminal

- Title, text and error messages appear on stderr. For each variable, "Label (name): " is asked, with the current value in `[square brackets]`. An empty input keeps the default or current value.
- `secret`: hidden input, nothing is displayed.
- `enum`: numbered list; enter the number or value, otherwise "Invalid choice. Enter a number or value."
- `bool`: "[y/n]", accepts y, yes, n, no.
- With several buttons, "Button: " follows with a numbered list (number or label); with one button the question is omitted.
- End of input (Ctrl+D) in a text field aborts the prompt: exit code 2.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Workflow finished successfully |
| 1 | Workflow failed |
| 2 | Aborted or rejected, also missing confirmation without a terminal |
| 3 | Input error: invalid file, prompt step without a terminal, `--var` not in the form `NAME=VALUE`, working directory missing, invalid variable value, workflow with a terminal step |

With `--cwd` you can put a run's files in a specific folder. Unlike the interface, `wts run` runs in the current directory by default, not in `~/.config/whattheshell/runs/ID`.

Workflows with terminal steps cannot be run with `wts run` (hint to use `wts gui`, exit code 3). `--dry-run` works.

## Terminal steps

Terminal steps run interactive programs such as `vim`, `less`, `top`, `ssh` in the browser. The terminal appears in the run panel.

- **Only in the interface.** Not with `wts run`.
- **Always in the sandbox.** Without `bwrap` the step does not start; a message with an installation hint appears, exit code 126.
- **Rights:** The program runs as a normal user in the sandbox: `/home`, `/root`, `/tmp`, `/var/tmp` and `/run` are empty or hidden, the rest of the file system is read-only. Only the step's working directory is writable (in the sandbox under `/tmp/work`). The working directory must be inside the run folder; other paths are rejected. `sudo`, `su` and `pkexec` do not work.
- **Network:** No network by default. The field "Allow network access" (`network`) permits it; the step then counts as "caution".
- **At most 4 terminals at the same time.** Further ones are rejected: "Too many terminals at once (limit reached). End one and start again."
- **One connection per terminal.** If the terminal is already connected in another tab, a message appears.
- **Time limits:** The step's timeout; 15 minutes without input or output end the terminal. If the browser does not connect within 600 seconds, the step ends with exit code 124 ("No terminal connected").
- **Ending:** Disconnecting or closing the page ends the program. There is no reconnecting.
- **Operation:** The keyboard goes to the program, Ctrl+C ends it. Esc, then Tab leaves the terminal. After the end, the content stays read-only until "Close" is chosen; the next terminal step replaces it.
- **Output:** It does not go to later steps. `{{ step.stdout }}` is empty; the exit code is in `{{ step.exit_code }}`. To pass text on, write a file into the working directory.
- **Clipboard and title:** Escape sequences from a program for clipboard, window title and hyperlinks are discarded.
- **Keystrokes** are not stored anywhere.

### Transcript

In the dialog "Run workflow?" (only visible for workflows with a terminal step) there is the option "Save terminal output as transcript". Off by default.

- Only the program's output is saved, never keystrokes. Typed characters do, however, appear as echo in the output.
- During the run it says "Output is being saved".
- File: `~/.cache/whattheshell/terminal/RUN-STEP.txt` (folder readable only by the user). After the end, the interface shows the location ("Output saved as") and a "Delete" button.
- Secret values are masked line by line, on a best-effort basis. Character-by-character redraws (cursor jumps) can bypass masking.

On the command line:

```
wts terminal transcripts                      # Transkripte auflisten
wts terminal transcripts --delete NAME.txt    # eines löschen
```
