# WhatTheShell

Ein Linux-Programm mit grafischer Oberfläche, in dem man Kommandozeilen-Tools wie Bausteine
zu Workflows zusammenklickt, ausführt und die Ausgaben auswertet.

**Status:** Phase 0, nicht benutzbar.

## Entwicklung

```
uv sync --group dev
uv run wts --version
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

## Lizenz

Code: AGPL-3.0-or-later (siehe `LICENSE`). Mitgelieferte Module (`modules/`) und
Workflows (`workflows/`): CC0-1.0.
