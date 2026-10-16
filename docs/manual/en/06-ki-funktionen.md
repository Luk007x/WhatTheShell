# AI features

The AI features are optional and **off by default**. As long as they are off, there are no network connections, no foreign processes and no AI code is even loaded. The buttons "Improve with AI" and the like then only show "AI off" ("AI features are switched off. Enable them in settings.").

An AI can make suggestions. It never executes anything: every answer arrives as a diff for approval, and the suggestion is only saved once you apply it.

## Enabling

- In the interface: gear, section "AI features (optional)", "Enable AI features", set the source, "Save".
- On the command line: `wts ai enable`; switch off with `wts ai disable`; view the settings with `wts ai status` (without key).

The settings are in `~/.config/whattheshell/settings.yaml` (readable only by the user). Keys are **never** in this file.

## Sources

The "Provider" determines where the request goes.

### Local model

A model server on your own machine (Ollama, llama.cpp, LM Studio or another OpenAI-compatible server).

| Field | Meaning |
|---|---|
| Endpoint | Address of the model server. The default `http://127.0.0.1:11434/v1` is Ollama |
| Model | Name as the endpoint lists it, e.g. `llama3` |
| Time limit (seconds) | Default 120 |

### Cloud API

| Field | Meaning |
|---|---|
| Protocol | `anthropic` or `openai` (`openai` also applies to compatible providers) |
| Endpoint (optional) | Empty = the provider's default |
| Model | Required field, e.g. `claude-sonnet-5-5`. The check reports an empty value |
| Environment variable of the key | Name of the variable, never the key itself. Default `ANTHROPIC_API_KEY` |
| Key status | "set" or "missing" |
| Key source | "Environment variable" or "System keyring" (needs the extra `whattheshell[keyring]`) |
| Time limit (seconds) | Default 120 |

### Installed agent program

Calls a program installed on the machine: Claude Code (`claude`) or Codex (`codex`).

| Field | Meaning |
|---|---|
| Program | `claude` or `codex`; next to it "found" (with path) or "not installed" |
| Call line (optional) | Empty = built-in call. One line per argument. Placeholders `{system}` = system instruction, `{tmp}` = empty working folder. Example for another model: `claude`, `-p`, `--model`, `sonnet`, … |
| Time limit (seconds) | Default 300 |

If the program is not in the `PATH`, it says: "Program not on PATH. See `wts ai check` for installation."

### Command outputs

"Send command outputs to the AI": Off (default) = only help texts and module and workflow files are sent. On = also stdout and stderr from runs, which may contain file names or data.

## Keys

Keys are never stored in files. There are two sources:

- **Environment variable:** The name is in the settings. The variable must be set in the server's environment, so it must be exported **before** `wts gui start`:

```
export ANTHROPIC_API_KEY=…
wts gui start
```

- **System keyring:** Install the extra `whattheshell[keyring]` for this and choose "System keyring" as the source.

The settings file rejects fields with "key" in the name and values that look like a key. A key from the environment is masked in the preview, error messages and answers; a key from the keyring is not masked and only appears in an error message if the provider itself echoes it back.

## Tasks

| Task | In the interface | Command line |
|---|---|---|
| Improve a module | Module editor: "Improve with AI" | `wts ai improve-module TOOL` |
| Add examples | Module editor: "Generate examples with AI" | `wts ai examples TOOL` |
| Workflow draft from a description | File menu: "Draft from description (AI)", fields "Description" and "File name (optional)" | `wts ai draft-workflow "DESCRIPTION" [--name NAME]` |
| Diagnosis of a failed step | On the failed step in the run's output: "Analyze cause (AI)" | `wts ai diagnose RUN.json STEP_ID` (file = output of `wts run --json`) |

The basis for "Improve a module" and "examples" is your own module file, otherwise a scaffold from the detected help.

## What is sent

Every task runs in two steps.

1. **Preview:** A dialog shows the system and user text **in full** with the character count ("n characters"). It says: "This data will be sent to the AI. Nothing is sent before you choose “Send”." For the diagnosis, you can tick "Include command outputs".
2. **Send:** Only "Send" sends the request. "Cancel" discards it.

Without command outputs, only the command, exit code, duration and status go out for the diagnosis, not a single line of output. With outputs, these are truncated. The value of the key variable is masked in the preview.

The preview shows what WhatTheShell sends. What an agent program itself loads or sends to its provider, it does not show.

On the command line, every task shows the preview and asks before sending; `--yes` confirms sending, `--preview-file FILE` writes the preview to a file instead of standard output. Without a terminal and without `--yes` it aborts. With `--include-output` (diagnosis only) outputs are sent along.

## Answer: diff, never executed

- The answer is extracted from the text and checked with the same rules as any module or workflow file. "Valid: yes" or "Valid: no" shows the result.
- The dialog shows the "Changes" as a diff ("added", "removed").
- If a suggestion lowers the safety class of a command or option, the diff is preceded by "WARNING: safety class … lowered".
- "Apply" loads a draft into the editor; it is then not yet saved. "Discard" throws it away.
- On the command line: `--apply` writes the result into the user folder without asking; without `--apply` it says "Nothing saved". `--yes` only permits sending, not writing.
- Writing happens only into your own folder `~/.config/whattheshell/modules` or `workflows`, with a plain file name, never into subfolders. The file is readable only by the user.
- The diagnosis returns plain text. It is not executed.

Answers are not trustworthy: help texts, module files or outputs sent along can influence the suggestion (prompt injection). So read the diff before you apply it. Whoever applies it unread with `--apply` takes on the risk.

## Isolation of the agent programs

Claude Code and Codex run restricted:

- In a **throwaway HOME**: a temporary folder readable only by the user, with its own `home/` and `work/`. The user's configuration (global `CLAUDE.md`, settings, hooks, plugins, skills, Codex `config.toml`) is not present there. Only the login file (`~/.claude/.credentials.json` or `~/.codex/auth.json`) is copied, if present.
- **Without write access** to the user's files. Claude additionally **without tools**; Codex in `read-only` mode.
- The folder including session files is deleted after every call, also on timeout and error.
- The prompt goes via standard input, not via the command line. The environment is cleaned, supplemented by the agent's key variable and proxy variables.
- The answer is limited to 2 MiB.

Residual risks:

- Codex in `read-only` mode can read the whole disk; an injected prompt could send data to the provider that the preview does not show.
- The login credentials are accessible to the agent (needed for the call). Settings that the provider keeps on the account still apply.
- If the credentials are not in a file (e.g. in a keyring), the agent is not logged in within the throwaway HOME; the check reports this. Remedy: `ANTHROPIC_API_KEY` or `claude login` / `codex login`.

## Checking with `wts ai check`

```
wts ai check               # prüft die eingestellte Quelle
wts ai check --no-network  # ohne einen Endpunkt zu kontaktieren
```

Depending on the provider, the check verifies: reachability of the endpoint, whether the model exists, whether the key is set, whether the agent program is installed and logged in. Every result appears as a line with a hint for the next step. Exit code 0 means: all fine, 1: something is missing. If AI is off, the check reports "AI off" without loading or contacting anything.

Agent programs are always started during the check (version and login check in the throwaway HOME), even with `--no-network`. The login check does not pass on the status output (with email address).

Settings can also be changed on the command line:

```
wts ai config set provider agent
wts ai config set agent.kind codex
wts ai config set api.model MODELLNAME
wts ai config set api.key_env MEINE_VARIABLE
wts ai config set send_outputs true
```

## Further limits

- At most two provider calls run at the same time; otherwise "AI busy. Try again later."
- Error responses from the provider are truncated and stripped of control characters; answers are limited to 2 MiB. Redirects are not followed.
- Errors at the provider appear as "Provider error".
