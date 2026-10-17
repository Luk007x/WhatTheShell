# Interface

The interface consists of a header, a mode bar, three columns (catalog, center, details) and a footer area with a status line and output. You can change the column widths by dragging the dividers with the mouse or with the keyboard (focus the divider, Left/Right arrow, with Shift in large steps, Home/End). The widths are remembered.

## Header

From left to right:

| Element | Effect |
|---|---|
| Name "WhatTheShell" | Title of the application |
| File (only in "Build") | "New", "Open", "Save", "Save as", "Delete"; shows the workflow name and "unsaved" when there are changes |
| Undo / Redo (only in "Build") | Undoes or restores changes to the workflow |
| Sandbox status | "Sandbox ready", "Sandbox unavailable" or "Sandbox status unknown". Without a sandbox there is no preview and there are no terminal steps |
| Manual (book icon) | Opens this manual. The header then shows "← Back", which returns to the interface |
| Help (question mark) | Opens the help dialog with the sections "Getting started", "Building a workflow", "Running and safety", "Modules", "Terminal", "AI features", "Keyboard shortcuts" |
| Appearance (icon) | Each click cycles between "system", "light" and "dark"; the tooltip reads "Appearance: system (click for light)" or similar. "system" follows the operating system setting |
| Gear | Opens the "Settings" |

On the very first start the help opens automatically. Small question-mark buttons in the headers of catalog, canvas, variables, run and modules jump directly to the matching help section.

## Mode bar

| Element | Effect |
|---|---|
| Build | Build workflows |
| Run | Start saved workflows |
| Modules | View and edit modules |
| Graph / Blocks | Only in "Build" mode: two views of the same workflow |

The last chosen mode and view are remembered. Which view appears when the app opens can be set in the settings ("View on start").

## Catalog (left)

The catalog lists the tools on the machine.

- **Search:** The "Search tools" field filters by name.
- **Favorites:** The star next to a tool marks it as a favorite. Favorites appear at the top under "Favorites", all others under "Other".
- **Category:** A coloured header on the step shows the category of the tool (e.g. text, files, network), provided a module specifies one. Condition, loop and helper steps have their own colours.
- **Coloured dots:** The dot before the name shows the safety class: "safe", "caution" or "dangerous".
- **"Terminal" badge:** The tool is interactive (e.g. `vim`, `less`, `top`, `ssh`) and runs as a terminal step in the terminal.

A tool is added by dragging it onto the canvas or with Ctrl+Enter in the catalog. Enter or a click only selects it.

## Canvas (center)

Shows the workflow. In the graph, steps are nodes; in the blocks view, they are nested cards (see the chapter "Building a workflow").

Above the canvas is the toolbar with "New", the "Name" field, the "Add: NAME" button (inserts the tool chosen in the catalog), the control blocks (If, Loop, Set variable, Wait, Message, Prompt, Abort), the "Target" selector ("at the end", "into “Then”", "into “Else”", "into “Loop”") and "Delete". The "Legend" on the canvas explains edges, ports and colours.

If the canvas is empty, it says: "Drag a tool from the catalog here, or insert it there with Ctrl+Enter."

## Details (right)

- **Nothing selected:** The workflow's variables ("Variables").
- **A step selected:** The form of that step (command, options, standard input, error handling, preview). Below it is the finished command, ready to copy ("Copy"), with its "Safety class".

Details on all fields: chapter "Building a workflow".

At the top right of the area, "Open details in a window" (arrow icon) opens the same content (step fields or variables table) in a large dialog with multi-column fields. "Back to the sidebar" or Esc closes it. The column width can still be changed by dragging the divider, up to half the window width.

## Output (bottom)

The output shows live output, messages and the plan of a run, per step. "Show output" and "Hide output" expand and collapse the area. Until the first run it says "No output yet." The status line reports connection errors and notices ("Workflow valid" or "n errors in workflow").

## Keyboard shortcuts

They apply in "Build" mode, not in form fields and open dialogs. Ctrl also counts as Cmd. Ctrl+S is intercepted in all modes (but only saves in "Build"), and `?` applies in all modes and shows the same table in the app.

| Key | Effect |
|---|---|
| Delete / Backspace | Delete the selected step (Ctrl+Z undoes it) |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z / Ctrl+Y | Redo |
| Ctrl+S | Save (opens the Save dialog; without a file, "Save as") |
| Esc | Clear selection and notice |
| Ctrl+Enter (in the catalog) | Append the tool at the chosen target |
| ? | Open help (shortcuts) |
| Drag | Catalog entry or control block onto the canvas: a step is created at the drop position |

In the blocks view, the following also apply on the focused block: Alt+Up/Down arrow (move), Alt+Right arrow (into the preceding container), Alt+Left arrow (out, after the container), Delete/Backspace (delete, without confirmation), Enter (select). In a terminal step, you leave the terminal with Esc, then Tab.

There is a "Skip to main content" link as the first focusable element, and all dialogs can be closed with Esc.

## Settings

The gear opens the settings.

### General

| Field | Values | Effect |
|---|---|---|
| Language | Deutsch, English | Language of the interface. The same choice applies to messages from the server and the `wts` command line (it is stored as `language` in `settings.yaml`; `wts --lang` and `WTS_LANG` take precedence) |
| Font size | small, normal, large | Scales all text |
| View on start | Last used, Build: graph, Build: blocks, Run, Modules | Takes effect the next time the app is opened |
| Run preview automatically | on/off | Only for commands of class "safe" and only with a chosen example; always runs in the sandbox |

### Program

The "Quit WhatTheShell" button stops the server (after a confirmation). Running workflows are cancelled.

### AI features (optional)

Off by default. As long as "Enable AI features" is not ticked, there are no network connections and no foreign processes. Details in the chapter "AI features".

| Field | Meaning |
|---|---|
| Enable AI features | Switches the features on or off |
| Provider | Local model (Ollama, llama.cpp, LM Studio, OpenAI-compatible), Cloud API (Anthropic or OpenAI-compatible) or Installed agent program (Claude Code or Codex) |
| Endpoint (Local model) | Address of the model server; the default `http://127.0.0.1:11434/v1` is Ollama |
| Model | Name of the model as the endpoint lists it (local), or required field for the cloud API |
| Protocol (Cloud API) | `anthropic` or `openai`; `openai` also applies to compatible providers |
| Endpoint (optional) | Empty = the provider's default |
| Environment variable of the key | Name of the variable, never the key itself. The server needs it in its environment: export it before `wts gui start` |
| Key status | "set" or "missing" |
| Key source | Environment variable or System keyring (needs the extra `whattheshell[keyring]`) |
| Program (for "Installed agent program") | `claude` or `codex`, shown as "found" (path) or "not installed" |
| Call line (optional) | Empty = built-in call. One line per argument; placeholders `{system}` and `{tmp}` |
| Time limit (seconds) | Wait time for the answer |
| Send command outputs to the AI | Off = only help texts and module/workflow files are sent. On = also stdout/stderr from runs |

The "Save" button in this section writes the AI settings to `~/.config/whattheshell/settings.yaml`.

Language, font size, appearance, start view, the preview option and favorites are not in this file but in the browser (chapter "Files and locations").
