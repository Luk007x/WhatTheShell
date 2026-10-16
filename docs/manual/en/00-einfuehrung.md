# Introduction

WhatTheShell is a graphical toolkit for terminal workflows. Command-line tools such as `grep`, `find`, `nmcli` or `rsync` become building blocks in a browser interface. You can click them together into sequences, run them and evaluate their output. The finished workflow is a YAML file that you can save, reuse and share with others.

The program runs locally on your own machine. The interface is served by a small server on `127.0.0.1` and opened in your normal browser (see the chapter "Installation and start").

## What WhatTheShell can do

- Find tools on the machine (all programs in the `PATH`) and show their options as a form. The options are read from the tool's help (`--help`). Bundled and custom modules improve this detection.
- Build workflows as a graph (nodes and edges) or as nested blocks. Both views show the same workflow.
- Pass the output of one step to the next, branch with conditions and repeat over the lines of an output.
- Look at commands before running them, check them with a dry run and explicitly confirm risky steps.
- Run interactive programs such as `vim`, `less` or `top` as a terminal step in the browser, always in a sandbox.
- Optional (off by default): AI features that suggest modules or workflows.

## Basic terms

| Term | Meaning |
|---|---|
| Tool | A program on the machine, e.g. `grep`. Listed in the catalog on the left. |
| Module | A YAML file that describes a tool: labels, groups, examples, safety class. Without a module, everything comes from the tool's help. |
| Workflow | A sequence of steps, saved as `*.workflow.yaml`. |
| Step | A building block of the workflow: a command, a terminal step or a control block (condition, loop, set variable, wait, message, prompt, abort). |
| Variable | A named value that is asked for when the workflow starts and is used in fields as `{{ var.name }}`. |
| Run | One execution of a workflow with concrete values. Runs are gone once the server stops. |
| Sandbox | An isolated environment (`bwrap`, bubblewrap) for the preview, module examples and terminal steps: no network, only one writable folder. |
| Safety class | Classification of a command: safe, caution or dangerous. It determines whether you are asked before the start. |

## The three modes

| Mode | Purpose |
|---|---|
| Build | Build and edit workflows (graph or blocks). |
| Run | Start saved workflows from the library, without the editor. |
| Modules | View and edit the descriptions of the tools. |

## A short example

Task: find lines containing `ERROR` in all log files of a folder and write a report if there are any matches.

1. In "Build" mode, search for `find` in the catalog and drag it onto the canvas.
2. Then add `grep` and `wc`. Draw a data edge (stdout → stdin) between `grep` and `wc`.
3. Create a condition that checks whether the line count is greater than 0.
4. Save with Ctrl+S. The workflow then appears in "Run" mode.

A similar workflow ships with WhatTheShell: "Fehler in Logs zählen" (Count errors in logs) (`log_errors`).

## What WhatTheShell is not

- Not a shell and not a script interpreter: commands are never run as a shell line, but as a list of arguments. Special characters in values have no effect.
- Not a server for other machines: the interface is only reachable via `127.0.0.1`, not from the network.
- Not a replacement for a terminal: terminal steps run in the sandbox; there is no terminal with the full rights of your user account.
- Not protection against everything: a confirmed command runs with the user's rights. The classification into safety classes is a heuristic based on names and options (chapter "Security").
- Not a program for root: starting as root is refused.
- Not a multi-user or cloud service; workflows and settings are stored as files in the user's folder.
- Not an automatic updater: you update with the package tool (chapter "Installation and start").

## Structure of this manual

| Chapter | Contents |
|---|---|
| Installation and start | Requirements, installation, starting, quitting, updating, uninstalling |
| Interface | Header, catalog, canvas, details, output, keyboard shortcuts, settings |
| Building a workflow | Steps, data flow, templates, variables, control blocks, saving |
| Running | Start form, confirmation, dry run, `wts run`, terminal steps |
| Modules | Module editor, custom modules, `wts scaffold` |
| AI features | Optional suggestions from a model |
| Security | What is protected and what is not |
| Files and locations | Storage locations and file formats |
| Troubleshooting | Typical messages and solutions |

The bundled example workflows carry German display names (shown in parentheses with an English translation in this manual).
