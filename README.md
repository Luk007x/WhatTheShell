# WhatTheShell

> Deutsche Dokumentation: Handbuch in der App (Buch-Symbol) und [auf GitHub](https://github.com/Luk007x/WhatTheShell/tree/main/docs/manual/de).

WhatTheShell is a Linux program with a graphical interface in which you click command-line tools together
like building blocks into workflows, run them, and evaluate their output. Everything runs locally; previews
and interactive programs are always executed inside a `bubblewrap` sandbox.

**Status:** beta. CLI, web GUI with node graph and block view, module editor, user prompts in runs, optional AI
features, embedded terminal for interactive programs, in-app manual (English and German).

## What it does

- Finds installed CLI tools and reads their options, types and help texts (with a confidence rating).
- Describes tools as modules (YAML), which you can scaffold, validate and hot-reload.
- Composes modules into workflows in a node graph or block view, with a dry-run plan that shows danger classes.
- Runs workflows with confirmation for `caution` and `dangerous` steps and evaluates the output.
- Runs module examples and previews in a sandbox (`bwrap`).
- Embedded terminal for interactive programs such as `vim`, `less` or `top` (GUI only, always sandboxed).
- Optional AI features (off by default): improve modules, draft workflows, diagnose failures.

## Requirements

Linux, Python >= 3.11, and `bubblewrap` (`bwrap`) for previews, examples and terminal steps (interactive
programs run only in the GUI, always in the sandbox; rules in `docs/SECURITY.md`, section 7).

Tested on Ubuntu (CI) and Fedora (development). The code contains nothing distribution-specific; only `bwrap`,
`setsid` and `prlimit` (util-linux) are needed. `wts sandbox` shows what is missing, with the install command
for your distribution.

## Install

```
sudo apt install bubblewrap pipx          # or your distribution's package manager
pipx install whattheshell
wts gui
```

Or from a wheel (CI artifact / release): `pipx install ./whattheshell-0.0.1-py3-none-any.whl`.

Node is only needed for building, not at runtime: the wheel contains the finished frontend.

## Start and stop

```
wts gui start               # start in the background, open the browser (if already running: browser only)
wts gui status              # port, PID, uptime; exit code 3 = not running
wts gui stop                # stop (SIGTERM, SIGKILL after 5 s)
wts gui                     # foreground, Ctrl+C stops; a second `wts gui` does not start a second server
wts gui --install-desktop   # menu entry "WhatTheShell" (~/.local/share/applications), calls `wts gui start`
```

State: `$XDG_RUNTIME_DIR/whattheshell/gui.json`; background server log: `~/.cache/whattheshell/gui.log`.

## Quick CLI overview

```
wts tools --search grep          # find installed tools
wts inspect grep                 # options, types, help texts, confidence (modules included)
wts scaffold wc --user           # module skeleton in ~/.config/whattheshell/modules/
wts validate file.module.yaml    # check a module or workflow
wts modules [--watch]            # loaded modules, hot reload
wts sandbox                      # bwrap self-test with install hint
wts example grep                 # run module examples in the sandbox
wts run workflow.yaml --dry-run  # plan with danger classes, nothing is executed
wts workflows                    # library: bundled, ~/.config/whattheshell/workflows, ./.whattheshell/workflows
wts run workflow.yaml|ID         # run with confirmation for caution/dangerous steps
wts gui                          # web UI on 127.0.0.1 with session token
wts ai status                    # AI features (off by default): enable, check, config set, improve-module, examples, draft-workflow, diagnose
wts terminal transcripts         # list transcripts of terminal steps, --delete NAME removes one
```

## Security in five bullets

- No shell: commands are never built by string concatenation and never run with `shell=True`.
- Commands are always an `argv` list; display uses `shlex.quote` only. Workflow files are untrusted and never executed on load.
- Previews, examples and the embedded terminal run only inside a `bwrap` sandbox; there is no unprotected fallback.
- The web API listens on `127.0.0.1` only, with a session token and Origin/Host checks, no CORS, never as root.
- AI is off by default, its code path is unreachable while off, and its answers are untrusted: never executed, only shown as a diff for approval.

Details: `docs/SECURITY.md`.

## Documentation

- In-app manual (book icon), available in English and German.
- On GitHub: [user manual](https://github.com/Luk007x/WhatTheShell/tree/main/docs/manual),
  [formats](https://github.com/Luk007x/WhatTheShell/blob/main/docs/FORMATS.md),
  [module authoring](https://github.com/Luk007x/WhatTheShell/blob/main/docs/MODULE_AUTHORING.md),
  [security concept](https://github.com/Luk007x/WhatTheShell/blob/main/docs/SECURITY.md),
  [architecture](https://github.com/Luk007x/WhatTheShell/blob/main/docs/ARCHITECTURE.md),
  [decisions](https://github.com/Luk007x/WhatTheShell/blob/main/docs/DECISIONS.md).

## Updating

```
wts gui stop                              # stop the running server (running workflows are aborted)
pipx upgrade whattheshell                 # or uv tool upgrade whattheshell / pip install -U whattheshell
wts gui start
```

Settings (`~/.config/whattheshell`), your own modules and workflows are kept; they live outside the package.
There is deliberately no update from within the running app (see `docs/DECISIONS.md`, D-017).

## Release and development

`git tag vX.Y.Z && git push --tags` builds the wheel and attaches it to the GitHub release.
Every release ships a CycloneDX SBOM (`wts --sbom`). Publishing to PyPI locally: `scripts/build_wheel.sh && uv publish dist/*`. Step by step: `docs/RELEASING.md`.

```
uv sync --group dev
uv run wts --version
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

## License

Code: AGPL-3.0-or-later (see `LICENSE`). Bundled modules and workflows (`src/whattheshell/bundled/`): CC0-1.0.
Security concept: `docs/SECURITY.md`.
