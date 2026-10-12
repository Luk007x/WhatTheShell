// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure helpers of the AI flow (F-27..F-30): output stripping, diff display, apply gate.
import type { AiResult, RunEvent } from "../types/api";

export type Step = Record<string, unknown>;
export interface DiffLine { kind: "add" | "del" | "meta" | "ctx"; text: string }

/** Without `include`, stdout/stderr never leave the browser (the server strips them as well). */
export const stripOutputs = (step: Step, include: boolean): Step =>
  include ? step : Object.fromEntries(Object.entries(step).filter(([k]) => k !== "stdout" && k !== "stderr"));

export function diffLines(diff: string): DiffLine[] {
  if (diff === "") return [];
  const lines = diff.split("\n");
  if (lines[lines.length - 1] === "") lines.pop();
  return lines.map((text): DiffLine => {
    if (text.startsWith("+++") || text.startsWith("---") || text.startsWith("@@")) return { kind: "meta", text };
    if (text.startsWith("+")) return { kind: "add", text };
    if (text.startsWith("-")) return { kind: "del", text };
    return { kind: "ctx", text };
  });
}

/** Only a valid module/workflow proposal can be applied; modules also need a target file. */
export const canApply = (r: AiResult): boolean =>
  r.valid && (r.kind === "workflow" || (r.kind === "module" && r.target !== null));

/** StepResult-like object of the last attempt of `stepId`, built from `GET /api/runs/{id}` events. */
export function stepFromEvents(events: RunEvent[], stepId: string): Step {
  let step: Step = { step_id: stepId };
  let out: string[] = [];
  let err: string[] = [];
  for (const e of events) {
    if (e.step_id !== stepId) continue;
    if (e.type === "step_started") { step = { step_id: stepId, command: e.command }; out = []; err = []; }
    else if (e.type === "output" && typeof e.text === "string") (e.stream === "stderr" ? err : out).push(e.text);
    else if (e.type === "step_finished") step = { ...step, exit_code: e.exit_code, ok: e.ok, duration: e.duration, attempts: e.attempt };
  }
  return { ...step, stdout: out.join("\n"), stderr: err.join("\n") };
}
