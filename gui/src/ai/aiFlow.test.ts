// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import type { AiResult } from "../types/api";
import { canApply, diffLines, stepFromEvents, stripOutputs } from "./aiFlow";

test("stripOutputs removes stdout/stderr unless included", () => {
  const s = { step_id: "a", ok: false, stdout: "x", stderr: "y" };
  expect(stripOutputs(s, false)).toEqual({ step_id: "a", ok: false });
  expect(stripOutputs(s, true)).toBe(s);
});

test("diffLines classifies lines", () => {
  expect(diffLines("--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n same\n")).toEqual([
    { kind: "meta", text: "--- a" }, { kind: "meta", text: "+++ b" }, { kind: "meta", text: "@@ -1 +1 @@" },
    { kind: "del", text: "-old" }, { kind: "add", text: "+new" }, { kind: "ctx", text: " same" },
  ]);
  expect(diffLines("")).toEqual([]);
});

test("canApply needs valid and a module target", () => {
  const r: AiResult = { kind: "module", raw: "", errors: [], diff: "", target: "wc.module.yaml", valid: true };
  expect(canApply(r)).toBe(true);
  expect(canApply({ ...r, valid: false })).toBe(false);
  expect(canApply({ ...r, target: null })).toBe(false);
  expect(canApply({ ...r, kind: "text" })).toBe(false);
  expect(canApply({ ...r, kind: "workflow", target: null })).toBe(true);
});

test("stepFromEvents keeps the last attempt", () => {
  const ev = [
    { type: "step_started", step_id: "a", command: "ls" }, { type: "output", step_id: "a", stream: "stdout", text: "old" },
    { type: "step_started", step_id: "a", command: "ls" }, { type: "output", step_id: "a", stream: "stderr", text: "boom" },
    { type: "output", step_id: "b", stream: "stdout", text: "other" },
    { type: "step_finished", step_id: "a", exit_code: 2, ok: false, duration: 0.1, attempt: 2 },
  ];
  expect(stepFromEvents(ev, "a")).toEqual({ step_id: "a", command: "ls", exit_code: 2, ok: false, duration: 0.1, attempts: 2, stdout: "", stderr: "boom" });
});
