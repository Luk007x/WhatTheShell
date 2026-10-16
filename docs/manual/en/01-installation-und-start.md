# Installation and start

## Requirements

| Requirement | Used for |
|---|---|
| Linux | The program is built for Linux. It is tested on Ubuntu and Fedora; nothing distribution-specific is needed. |
| Python 3.11 or later | Runtime of the program. |
| `bubblewrap` (`bwrap`) | Sandbox for the preview, module examples and terminal steps. Without `bwrap` there is no preview and there are no terminal steps. |
| `util-linux` (`setsid`, `prlimit`) | Needed by the sandbox and the terminal steps. If `prlimit` is missing, the sandbox runs with a warning and without memory and process limits. |
| Browser | The interface runs in the browser. |

Node.js is only needed to build the interface, not at runtime: the package contains the finished interface.

The sandbox needs unprivileged user namespaces. Where these are blocked (e.g. by AppArmor or a system setting), the sandbox is not available.

## Installation

```
sudo apt install bubblewrap pipx          # bzw. der Paketmanager der Distribution
pipx install whattheshell
```

If the package is not yet published on PyPI, you can install a wheel directly:

```
pipx install ./whattheshell-0.0.1-py3-none-any.whl
```

Afterwards the `wts` command is at `~/.local/bin/wts` (the program itself: `~/.local/share/pipx/venvs/whattheshell`).

### Checking that everything is present

```
wts sandbox
```

`wts sandbox` runs a self-test of the sandbox. If something is missing, the output shows the installation command for your distribution. In the interface, the header shows "Sandbox ready" or "Sandbox unavailable".

## Starting

| Command | Effect |
|---|---|
| `wts gui start` | Starts the server in the background and opens the browser. If an instance is already running, only the browser is opened. |
| `wts gui status` | Shows port, PID and uptime. Exit code 3 means: not started. |
| `wts gui stop` | Stops the server (SIGTERM, SIGKILL after 15 s). Running workflows are cancelled. |
| `wts gui` | Starts in the foreground. Ctrl+C stops it. A second `wts gui` does not start a second server. |
| `wts gui --port N` | Fixed port number instead of a free port. |
| `wts gui --no-browser` | Do not open the browser; the address is printed. |
| `wts gui --install-desktop` | Creates the "WhatTheShell" menu entry. |

The server opens the browser through a short private redirect page. This keeps the session token out of the process list.

### Language of messages

Messages from the server and the `wts` command line follow the chosen language. On the command line, `wts --lang de` or `wts --lang en` sets it for one call, the environment variable `WTS_LANG` for the session; without either, the system language is used, and English if that is neither German nor English. The interface language is set in the settings ("Language").

### Menu entry

```
wts gui --install-desktop
```

writes `~/.local/share/applications/whattheshell.desktop` (or under `$XDG_DATA_HOME/applications`). The entry calls `wts gui start`. It then appears in the application menu under the name "WhatTheShell".

### Session token and `127.0.0.1`

On start, the server generates a random session token. The address looks like this:

```
http://127.0.0.1:PORT/#token=…
```

- The part after `#` never goes to the server; the interface reads it in the browser and sends it along with every request.
- Without a token, the page shows: "Please start via `wts gui`. The address with the session token (#token=…) is missing."
- The token is only valid for this session. After a server restart there is a new one.
- The server binds exclusively to `127.0.0.1`. It is not reachable from the network. Why this matters: the server can run commands. If a foreign web page or another machine could reach it, it could trigger commands. The token and the check of host and origin of the requests prevent that.
- Starting as root is refused.

If you share the address with the token or look at the browser history: the token is only valid as long as the server is running.

### Quitting

- In the interface: Settings (gear), section "Program", button "Quit WhatTheShell". Running workflows are cancelled. Afterwards a message appears saying that the tab can be closed.
- On the command line: `wts gui stop`.
- Closing the browser tab does not stop the server.

## Updating

```
wts gui stop
pipx upgrade whattheshell        # bzw. uv tool upgrade whattheshell / pip install -U whattheshell
wts gui start
```

Settings (`~/.config/whattheshell`), custom modules and custom workflows are preserved because they are not part of the package. There is no update from within the running interface.

## Uninstalling

```
wts gui stop
pipx uninstall whattheshell
```

`pipx uninstall` leaves all user data in place. To remove it completely, also run:

```
rm -r ~/.config/whattheshell ~/.cache/whattheshell
rm ~/.local/share/applications/whattheshell.desktop     # falls der Menüeintrag angelegt wurde
```

This removes settings, custom modules and workflows, cache, background log and terminal transcripts. Back them up first if needed (chapter "Files and locations"). If the environment variables `XDG_CONFIG_HOME` or `XDG_CACHE_HOME` were set, the folders are located there instead of under `~/.config` and `~/.cache`.

The interface settings (language, appearance, start view, last entered values) are stored in the browser's local storage (`localStorage`) and can be deleted there via the site data for `127.0.0.1`.

## Where the state of the running instance lives

| File | Purpose |
|---|---|
| `$XDG_RUNTIME_DIR/whattheshell/gui.json` | PID, port and address of the running instance (fallback: `~/.cache/whattheshell/run/`) |
| `~/.cache/whattheshell/gui.log` | Log of the server started in the background |

`wts gui stop` only stops the process that really belongs to this file. A reused process number does not hit a foreign process.
