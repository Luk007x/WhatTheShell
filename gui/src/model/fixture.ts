// SPDX-License-Identifier: AGPL-3.0-or-later
// Test fixture: bundled example workflow log_errors as an object.
import type { Workflow } from "../types/workflow";

export const logErrors: Workflow = {
  schema_version: 1,
  name: "Fehler in Logs zählen",
  variables: { logdir: { type: "path", default: "./logs", label: "Log-Ordner" } },
  steps: [
    { id: "finde", tool: "find", args: { start: ["{{ var.logdir }}"], name: "*.log", type: "f" } },
    { id: "suche", tool: "grep", args: { patterns: "ERROR", recursive: true }, ok_exit_codes: [0, 1] },
    { id: "zaehle", tool: "wc", args: { lines: true }, stdin: { pipe: "suche" } },
    {
      id: "pruefe",
      kind: "if",
      condition: { source: "zaehle.stdout", number_gt: 0 },
      then: [{ id: "bericht", tool: "tee", args: { file: ["bericht.txt"] }, stdin: { text: "T:\n{{ suche.stdout }}\n" } }],
      else: [{ id: "ok", kind: "message", text: "Alles in Ordnung." }],
    },
  ],
  layout: { nodes: { finde: { x: 0, y: 0 } } },
};
