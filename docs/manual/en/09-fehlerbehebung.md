# Troubleshooting

## Where the logs are

| What | Where |
|---|---|
| Server running in the background via `wts gui start` | `~/.cache/whattheshell/gui.log` |
| Server in the foreground (`wts gui`) | Output in the terminal |
| Accesses | There is no access log (so that the token does not end up in a log) |

Error messages in the interface give the cause and a hint for the solution. Stack traces are not in the responses, only in the log.

## Sandbox and installation

### "Sandbox unavailable" / bubblewrap missing

Without `bwrap` there is no preview, no module examples and no terminal steps; there is no unprotected substitute.

1. Run `wts sandbox`. The output gives the reason and the distribution's installation command, e.g. `sudo apt install bubblewrap`.
2. In the interface, choose "Test again" (in the "Preview" area).
3. If `prlimit` or `setsid` is missing, install the package `util-linux`. Without `prlimit` the sandbox runs with a warning and without memory and process limits.
4. If `bwrap` is installed but the sandbox is still unavailable, unprivileged user namespaces are usually blocked (AppArmor or system setting). This can only be changed at system level.

### Terminal step does not start

Without a sandbox the step does not start; a message with the installation hint appears (exit code 126). See above.

## Start and connection

### "Already running on port N (PID P)"

An instance is already running. `wts gui start` or `wts gui` then only opens the browser. A second server is not started. Check the state:

```
wts gui status        # Exit-Code 3: nicht gestartet
wts gui stop          # beenden
```

If the process cannot be ended, `wts gui stop` gives the command `kill -9 PID`. For "Already running (state not yet readable)", wait a moment and repeat `wts gui status`.

### "Please start via `wts gui`. The address with the session token (#token=…) is missing."

The page was opened without a token, e.g. via a bookmark or after a server restart (the token changes with every start). Solution: call `wts gui start`. This opens the browser with a valid address. If the server runs in the foreground (`wts gui`), the address with the token is in the terminal output.

### "Port N not usable"

The given port is in use or not allowed. Choose a different one with `--port` or omit `--port` (a free port is then chosen).

### "Server not started. Cause in the log: …"

After 10 seconds, `wts gui start` did not find a running server. The reason is in `~/.cache/whattheshell/gui.log`. Alternatively start `wts gui` in the foreground, then the messages appear in the terminal.

### "Starting as root is refused"

The interface can run commands and therefore does not start as root. Start as a normal user.

### "Server unreachable: …"

The server was stopped (e.g. with `wts gui stop` or "Quit WhatTheShell"). Start it again with `wts gui start`.

### "Connection to the run lost."

The page lost the connection to the server; the server may no longer be running. Check `wts gui status` and restart if necessary. Runs are gone after a server restart.

### "State file not written" / "Instance lock not possible"

The folder for the state (`$XDG_RUNTIME_DIR/whattheshell` or `~/.cache/whattheshell/run`) is not writable or has wrong permissions. Check the permissions; the folder must belong to the user.

## Workflows

### "The file was changed outside the app" / the workflow does not start

The workflow is "Changed outside" or "Not reviewed" (see "Library: filter, import and integrity" in the chapter "Building a workflow"). Read the file, then click "Review and accept" in the library, or run `wts workflows accept ID` or `wts run --accept`. A dry run works without accepting. After an update, existing own files show "Not reviewed" once. Files outside the workflow folders always need `--accept`.

### Workflow invalid

In the interface it says "n errors in workflow"; the message names the field. On the command line:

```
wts validate DATEI
```

Typical causes:

- Duplicate or invalid id (`the id X already exists`, `Invalid id X`): ids consist of lowercase letters, digits and `_` and start with a letter.
- A template `{{ … }}` refers to a step that comes later or does not exist, or to an undeclared variable.
- A condition has no operator or several: exactly one is allowed.
- Unknown fields (typos). The message names the field path.
- Broken files appear greyed out in the library with `path:line: message`. Fix the file; the list reloads.

### Variable does not match the pattern

At start: "Does not match pattern …". The field shows "Pattern: …". The regex must match the whole value, not just a part. For the "WLAN auf 5 GHz fixieren" (Pin Wi-Fi to 5 GHz) workflow, for example, the BSSID must match the format `AA:BB:CC:DD:EE:FF`.

Further messages: "Required", "Whole number expected", "Number expected", "Pick a value from the list", "At least N", "At most N".

### "--var expects NAME=VALUE"

Variables are passed to `wts run` as `--var name=value`, e.g. `--var logdir=./logs`.

### "Confirmation required but no terminal"

`wts run` found risky steps and cannot ask (e.g. in a script). Confirm with `--yes` or check first with `--dry-run` (exit code 2).

### "Tool … not found on PATH"

The step's tool is not installed. The step carries the "Tool missing" marker in the graph and block view, and the step panel shows the hint. Install the tool; if the module has an install command, it is in the message ("Installation: …"). Otherwise check the spelling of the tool.

### "Working directory … does not exist"

Give an existing folder with `--cwd`.

### A step fails although it ran "correctly"

Some tools return exit codes other than 0 in normal operation, e.g. `grep` exit 1 for "no matches". In the step, set "Success exit codes" to `0, 1`.

### The plan changed since you confirmed it

The plan differs from the one confirmed before. Check the new plan and confirm again.

### Workflow with a terminal step cannot be started with `wts run`

Terminal steps only run in the interface (exit code 3). `--dry-run` is possible. Run it via `wts gui`.

## Terminal steps

| Message | Meaning and solution |
|---|---|
| "Too many terminals at once (limit reached). End one and start again." | At most 4 simultaneous terminals. End another one |
| "The terminal is already connected in another tab or window." | Only one connection per terminal. Close the other tab |
| "Terminal ended: time limit or too long without input and output." | The step's time limit was reached or 15 minutes of silence. Start again, raise the step's time limit if needed |
| "Terminal ended: the program prints output too fast." | The program sent too much data to the terminal. Start again |
| "Terminal not found (the step is no longer running)." | The step had already ended |
| "Terminal connection closed (code N). See the step messages for the cause." | Read the messages in the output area |
| "No terminal connected" | The browser did not connect within 600 seconds. Exit code 124 |
| The step ends without a terminal, exit code 126 | The sandbox is missing (see above) |

An ended terminal cannot be reconnected; reloading the page ends the program.

Transcripts are in `~/.cache/whattheshell/terminal/`. To view and delete: `wts terminal transcripts` and `wts terminal transcripts --delete NAME.txt`.

## Modules

### Module is not recognized

- The file name must end in `.module.yaml`, `.module.yml` or `.module.json`.
- The file must be in one of the search folders: `~/.config/whattheshell/modules/` or `<project>/.whattheshell/modules/` (the latter only if `wts` was started in the project folder). `wts modules` shows search paths and loaded modules.
- A faulty file is reported with path, line and field path and only it is disabled: `wts validate FILE`. In "Modules" mode, errors are under "Errors".
- A file over 1 MiB is rejected, as are YAML aliases and anchors.
- A file with an error in the editor: "YAML syntax error: …". Correct it in the raw text.
- `tool` must match the name of the program on the `PATH` (without path, without leading `-`).
- A project module is only loaded if `wts` was started in the project folder.
- An own module overrides a bundled one for the same tool. If the effect is missing, `wts inspect TOOL` shows the merged result.
- When merging, use the ids from `wts inspect TOOL --json`; an unknown id creates a new option instead of changing the existing one.

### Adapting a bundled module

Save the module as your own under the same tool; it then overrides the bundled one. "Delete" only removes own modules.

### Module example fails

`wts example TOOL` runs the examples in the sandbox and shows which expectation (`expect`) does not hold. Without a sandbox they are skipped.

## AI features

First run `wts ai check`. Every line gives a finding and a hint.

| Finding | Solution |
|---|---|
| "AI off" / "AI features are switched off." | Enable in the settings or `wts ai enable` |
| Model not entered ("no model set") | Enter it in the settings, or `wts ai config set local.model NAME` or `api.model NAME` |
| Endpoint not reachable (local) | Start the model server, e.g. `ollama serve`; check the address in the settings |
| Model not present | Load the model, e.g. `ollama pull NAME`; check the name |
| Key missing ("Key status: missing") | Set the variable named in "Environment variable of the key" and **restart** the server: export before `wts gui start` |
| Cloud API not reachable | Check network, proxy and endpoint |
| Agent program "not on PATH" / "not installed" | Install the program (`claude` or `codex`); `wts ai check` gives the command |
| "not logged in" | `claude login` or `codex login`. If the credentials are only in a keyring, set the key as an environment variable instead (e.g. `ANTHROPIC_API_KEY`) |
| "Login file cannot be copied" | Check the permissions of the login file in the home folder |
| "AI busy. Try again later." | Two requests are already running. Wait |
| "Provider error" | Read the provider's message; raise the time limit in the settings if it is down to the duration |
| "Valid: no" in the answer | The suggestion is not a valid file. Discard it or correct it in the editor; nothing is saved |

A key never belongs in the settings file. Values that look like a key are rejected there.

## Settings

### "Fix or delete the settings file"

The file `~/.config/whattheshell/settings.yaml` is invalid. Fix or delete it; the AI features are then off again (default).

## Other

### The interface shows only an error message, the API is running

The package does not contain the interface (installation from a source folder without the built interface). Install the program from the wheel or from PyPI with `pipx`.

### Resetting the interface settings

Delete the browser's site data for `127.0.0.1`. This resets language, font size, appearance, start view, favorites, column widths and remembered values. Files (modules, workflows) stay untouched.

### Resetting everything

```
wts gui stop
rm -r ~/.config/whattheshell ~/.cache/whattheshell
```

This also deletes your own modules and workflows. Back them up first (chapter "Files and locations").
