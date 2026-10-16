# Security

WhatTheShell runs commands on your own machine. This chapter describes what the program does to keep that from going wrong, and where the limits are.

## No shell, only argument lists

- Every command is started as a list of arguments, never as a shell line. Special characters such as `;`, `$()`, backticks, spaces or quotation marks in values therefore have no effect.
- The displayed command is quoted for display only; the list is what gets started.
- A value that starts with `-` may be read by the tool as an option. The program does not insert `--`, because not every tool knows it.
- A tool that itself starts a shell (`sh -c`, `xargs`) is not defused by this. Such tools are at least "caution".

## Workflow and module files are not trustworthy

Files from a foreign source count as foreign input.

- **Nothing is executed** on opening or loading. The file is only read and checked.
- Before the first run, the program shows all commands with safety class (plan).
- Files over 1 MiB, YAML aliases and anchors (protection against YAML bombs) and extremely deep nesting are rejected. A faulty file only disables itself.
- Templates `{{ … }}` only know references to values; there are no expressions, calls or filters.
- A terminal step has no preset keyboard input; the program rejects such fields.

Limits:

- There is no origin marking ("foreign file, never confirmed").
- Project modules and project workflows from `./.whattheshell/` are loaded without confirmation.
- Resolving a tool reads its help (`--help`); this starts the tool. For unknown subcommands this never happens. Tools such as `shutdown`, `reboot`, `halt`, `poweroff`, `init`, `telinit` and `kexec` are never queried this way. Other dangerous tools are not covered. The query runs in the sandbox as soon as it is available; tools under `/home`, `/root`, `/tmp`, `/var/tmp` and `/run` additionally run on the host.
- A malicious module can contain misleading descriptions or examples. The displayed command is nevertheless the one that runs.

## Safety classes and confirmations

| Class | Behavior |
|---|---|
| safe (`safe`) | Runs without asking |
| caution (`caution`) | Confirmation with plain command |
| dangerous (`dangerous`) | Confirmation with plain command and red confirm button |

- The highest applicable rule wins. Modules may classify higher, not lower than the built-in lists.
- The class is determined before the run and once more at runtime with the substituted values; the higher one applies.
- The dry run is always available and starts nothing.
- `sudo`, `su`, `doas`, `pkexec`, `chroot` are "dangerous". There is no silent `sudo`. `sudo` needs a terminal for the password, and the engine does not pass on a password.
- On the command line, `--yes` confirms everything without asking. This is intentional for scripts.

The classification is a heuristic based on names and options. It does not recognize:

- tools under a different name (symlink, script),
- danger that only lies in values (e.g. `dd of=/dev/sda`, target paths),
- bundled short options such as `-rf` (exception `sed -i…`),
- tools that internally call `sudo` or a shell.

Unknown tools stay "safe". If you want to classify a tool more precisely, write a module (chapter "Modules"). When in doubt, choose the higher class.

Real runs inherit the user's full environment (`HOME`, `PATH` …). Secrets in environment variables are visible to every program started. Memory and process limits of the sandbox do not apply to runs on the host.

## Sandbox

The preview of a step, module examples and terminal steps run in `bwrap` (bubblewrap).

| Property | Effect |
|---|---|
| File system | Mounted read-only; `/tmp`, `/var/tmp`, `/home`, `/root`, `/run` are empty. Only the working directory is writable (in the sandbox under `/tmp/work`) |
| Network | No network. Only a terminal step with `network: true` gets one |
| Processes | Own process namespace; ends with the program |
| Environment | Cleaned; fixed `PATH` |
| Limits | Preview: 10 s and 1 MiB of output; memory and processes via `prlimit` (512 MiB address space, 256 processes) |

**There is no fallback mode.** Without `bwrap` there is no preview, no examples and no terminal steps, instead of running them unprotected. `wts sandbox` shows the state and, if something is missing, the installation command.

Limits of the sandbox:

- `bwrap` needs unprivileged user namespaces; where these are blocked, the sandbox is unavailable.
- The file system is **readable**: `/home` is hidden, but `/etc`, `/usr` and data outside `/home` are readable.
- If `prlimit` is missing, the sandbox runs without memory and process limits (with a warning).
- The normal execution of a workflow ("Run" mode, `wts run`) does **not** run in the sandbox but with the user's rights. That is what the confirmations are for.

## Secrets

Variables of type `secret` are replaced by `***` in command display, output, messages and result, as well as in logs and AI previews. A secret must not have a default value and is not remembered in the browser.

Limits:

- The exact value is masked. Altered forms (Base64, URL-encoded, truncated) remain visible.
- A secret with a line break, output in pieces, can escape masking. The masking works line by line.
- A secret is in the program's argument list and is visible to other processes of the same user (`/proc/PID/cmdline`). It is better to pass it via the environment or standard input.
- In the terminal transcript, masking is best-effort; redraws with cursor jumps can slip through. Typed characters appear as echo.
- Error messages caused by a wrong variable type may contain the value; this has not been checked exhaustively.

## Local interface and API

| Protection | Effect |
|---|---|
| Only `127.0.0.1` | The server is not reachable from the network. No `0.0.0.0`, no IPv6 |
| Session token | 32 random bytes per start; every request needs it, otherwise it is rejected. The token is in the part after `#` of the address and does not go to the server |
| Host check | Only `127.0.0.1:PORT` and `localhost:PORT` are accepted (protection against DNS rebinding) |
| Origin check | Requests from other web pages are rejected (protection against cross-site requests) |
| No CORS | Other web pages may not read the API |
| No root | Starting as root is refused |
| No access log | The token does not end up in a log |
| Size limits | Requests up to 1 MiB |
| Run limits | at most 4 simultaneous runs, at most 2 simultaneous previews |

Not part of the protection:

- **Other processes of the same user.** They reach the port and can read the state file with the token. Protection against local attackers with the user's rights is not part of the model. Likewise an already compromised user account.
- Every browser tab with a valid token can answer confirmations; it is the same user.
- The first address with `#token=…` is in the browser history and in the terminal output. The token is only valid for this session. If the server is killed hard (`SIGKILL`), the redirect file with the token stays behind; it is readable only by the user and the token is then worthless.
- There is no Content Security Policy. The interface displays outputs as text and does not use `innerHTML`.

## Terminal steps

- Only in the interface, only as a normal user, always in the sandbox, at most 4 at a time, one connection per terminal. No terminal without a sandbox.
- No network except `network: true`; then at least "caution" and the confirmation text mentions "network access".
- The working directory must be inside the run folder, so that a foreign workflow file cannot, for example, mount `$HOME` writable.
- No setuid programs: `sudo`, `su`, `pkexec` do not work in the sandbox.
- Keystrokes are never stored or logged. A transcript only stores the output, only on request, readable only by the user.
- Escape sequences for clipboard (OSC 52), window title and hyperlinks are discarded.
- Disconnecting ends the program. There is no reconnecting.
- Time limits: that of the step, 15 minutes without input or output.
- The output of a terminal step does not go to later steps.

## AI off means no network

As long as the AI features are switched off (default), no AI code is loaded, there is no network connection and no foreign process. When on, nothing goes out until you choose "Send" in the preview. Answers are never executed, only shown as a diff for approval (chapter "AI features").

## Reporting security problems

Please report them as a GitHub issue with the label `security`. Do not post credentials, secrets or exploitable details publicly; a description of the kind of problem is enough. A response time is not promised.
