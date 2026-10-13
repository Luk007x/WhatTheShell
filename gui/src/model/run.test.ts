// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import type { RunEvent } from "../types/api";
import { slugify } from "./files";
import { logErrors as wf } from "./fixture";
import { findStep, captureOutput, evaluateOutput } from "./ops";
import { initialRun, reduceEvents } from "./run";

const play = (events: RunEvent[]) => events.reduce(reduceEvents, initialRun);

test("events are grouped per step and status changes", () => {
  const s = play([
    { type: "step_started", step_id: "a", command: "ls", safety: "safe" },
    { type: "output", step_id: "a", stream: "stdout", text: "x\n" },
    { type: "output", step_id: "a", stream: "stderr", text: "w\n" },
    { type: "step_finished", step_id: "a", exit_code: 0, ok: true, duration: 0.1, attempt: 1 },
    { type: "step_started", step_id: "b", command: "rm x", safety: "dangerous" },
    { type: "confirm_request", step_id: "b", command: "rm x", safety: "dangerous", reasons: ["löscht"] },
  ]);
  expect(s.status).toBe("running");
  expect(s.blocks.map((b) => b.id)).toEqual(["a", "b"]);
  expect(s.blocks[0]?.lines.map((l) => l.stream)).toEqual(["stdout", "stderr"]);
  expect(s.blocks[0]?.finish).toMatchObject({ ok: true, exit_code: 0 });
  expect(s.confirm).toMatchObject({ step_id: "b", reasons: ["löscht"] });
  const end = reduceEvents(s, { type: "finished", status: "aborted", message: "m", exit_code: 1 });
  expect(end).toMatchObject({ status: "aborted", confirm: null, message: "m", exitCode: 1 });
});

test("skipped, message, unknown events", () => {
  const s = play([{ type: "step_skipped", step_id: "c", reason: "else" }, { type: "message", step_id: "d", text: "hi" }, { type: "weird" }]);
  expect(s.blocks[0]?.skipped).toBe("else");
  expect(s.blocks[1]?.messages).toEqual(["hi"]);
});

test("slugify", () => {
  expect(slugify("Fehler in Logs zählen")).toBe("fehler-in-logs-zaehlen");
  expect(slugify("  Über Größe!! ")).toBe("ueber-groesse");
  expect(slugify("???")).toBe("workflow");
});

test("capture output adds variable and set step behind the step", () => {
  const r = captureOutput(wf, "suche");
  expect(r.wf.variables?.suche_out).toEqual({ type: "string" });
  expect(r.wf.steps.map((s) => s.id)).toEqual(["finde", "suche", "suche_set", "zaehle", "pruefe"]);
  expect(findStep(r.wf, "suche_set")?.step).toMatchObject({ kind: "set", variable: "suche_out", value: "{{ suche.stdout }}" });
  expect(r.created).toBe("suche_set");
});

test("evaluate output adds an if step in the same sequence", () => {
  const r = evaluateOutput(wf, "bericht");
  expect(findStep(r.wf, r.created ?? "")).toMatchObject({
    path: ["pruefe", "then"], index: 1,
    step: { kind: "if", condition: { source: "bericht.stdout", is_empty: false } },
  });
});

test("terminal_request opens, terminal_closed ends with exit code and transcript name", () => {
  const open = play([
    { type: "step_started", step_id: "t", command: "cat", safety: "safe" },
    { type: "terminal_request", step_id: "t", command: "cat" },
  ]);
  expect(open.terminal).toEqual({ stepId: "t", command: "cat" });
  expect(open.blocks[0]?.interactive).toBe(true);
  const closed = reduceEvents(open, { type: "terminal_closed", step_id: "t", exit_code: 0, transcript: "t.log" });
  expect(closed.terminal).toBeNull();
  expect(closed.terminalEnd).toEqual({ stepId: "t", exitCode: 0, transcript: "t.log" });
  expect(reduceEvents(open, { type: "terminal_closed", step_id: "t", exit_code: 1, transcript: null }).terminalEnd?.transcript).toBeNull();
});

test("terminal_request carries the server's transcript flag, absent stays absent", () => {
  expect(reduceEvents(initialRun, { type: "terminal_request", step_id: "t", command: "cat", transcript: true }).terminal?.transcript).toBe(true);
  expect(reduceEvents(initialRun, { type: "terminal_request", step_id: "t", command: "cat", transcript: false }).terminal?.transcript).toBe(false);
  expect(reduceEvents(initialRun, { type: "terminal_request", step_id: "t", command: "cat" }).terminal?.transcript).toBeUndefined();
});
