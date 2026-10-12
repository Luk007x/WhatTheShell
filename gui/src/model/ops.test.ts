// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import type { Workflow } from "../types/workflow";
import { logErrors as wf } from "./fixture";
import { addStep, findStep, getSeq, moveAfter, moveStep, newId, removeStep, renameStep, setLayout, stepIdAtErrorPath, updateStep, visibleSteps } from "./ops";

test("findStep and getSeq", () => {
  expect(findStep(wf, "ok")).toMatchObject({ path: ["pruefe", "else"], index: 0 });
  expect(getSeq(wf, ["pruefe", "then"])?.map((s) => s.id)).toEqual(["bericht"]);
  expect(getSeq(wf, ["nope", "then"])).toBeUndefined();
});

test("newId is unique and matches the pattern", () => {
  expect(newId(wf, "grep")).toBe("grep");
  expect(newId(wf, "suche")).toBe("suche_2");
  expect(newId(wf, "7z")).toBe("s_7z");
  expect(newId(wf, "var")).toBe("var_2");
});

test("addStep rejects duplicates and appends", () => {
  expect(addStep(wf, { id: "suche", tool: "ls" }, []).warnings).toHaveLength(1);
  const r = addStep(wf, { id: "ls", tool: "ls" }, [], 1);
  expect(r.wf.steps.map((s) => s.id)).toEqual(["finde", "ls", "suche", "zaehle", "pruefe"]);
  expect(wf.steps).toHaveLength(4); // immutable
});

test("removeStep removes layout and dangling pipes", () => {
  const r = removeStep(wf, "suche");
  expect(findStep(r.wf, "zaehle")?.step).not.toHaveProperty("stdin");
  expect(r.warnings).toHaveLength(1);
  expect(removeStep(wf, "finde").wf.layout?.nodes).toEqual({});
});

test("moveStep: no cycles, pipes need earlier steps", () => {
  expect(moveStep(wf, "pruefe", ["pruefe", "then"]).warnings[0]).toMatch(/^cycle/);
  const r = moveStep(wf, "suche", [], 4); // behind zaehle which pipes from it
  expect(r.wf.steps.map((s) => s.id)).toEqual(["finde", "zaehle", "pruefe", "suche"]);
  expect(findStep(r.wf, "zaehle")?.step).not.toHaveProperty("stdin");
  expect(moveAfter(wf, "finde", "suche").wf.steps.map((s) => s.id).slice(0, 2)).toEqual(["suche", "finde"]);
});

test("roundtrip add -> move -> remove restores the document", () => {
  const a = addStep(wf, { id: "x", kind: "wait", seconds: 1 }, []).wf;
  const b = moveStep(a, "x", ["pruefe", "else"], 0).wf;
  const c = moveStep(b, "x", ["pruefe", "then"], 0).wf;
  expect(removeStep(c, "x").wf).toEqual(wf);
});

test("updateStep patches, undefined deletes", () => {
  const r = updateStep(wf, "zaehle", { stdin: undefined, cwd: "/tmp" });
  expect(findStep(r.wf, "zaehle")?.step).toMatchObject({ cwd: "/tmp" });
  expect(findStep(r.wf, "zaehle")?.step).not.toHaveProperty("stdin");
  expect(updateStep(wf, "zaehle", { stdin: { pipe: "pruefe" } }).warnings).toHaveLength(1);
});

test("renameStep updates references", () => {
  const r = renameStep(wf, "suche", "such").wf;
  expect(findStep(r, "zaehle")?.step).toMatchObject({ stdin: { pipe: "such" } });
  expect(JSON.stringify(r)).toContain("{{ such.stdout }}");
  expect(JSON.stringify(r)).not.toContain("suche");
  expect(renameStep(wf, "suche", "finde").warnings).toHaveLength(1);
  const c = renameStep(wf, "zaehle", "n").wf;
  expect(findStep(c, "pruefe")?.step).toMatchObject({ condition: { source: "n.stdout" } });
});

test("setLayout, visibleSteps, error paths", () => {
  expect(setLayout(wf, "ok", { x: 1, y: 2 }).layout?.nodes?.ok).toEqual({ x: 1, y: 2 });
  expect(visibleSteps(wf, "bericht")).toEqual(["finde", "suche", "zaehle"]);
  expect(stepIdAtErrorPath(wf, "steps[3].if.else[0].message.text")).toBe("ok");
  expect(stepIdAtErrorPath(wf, "steps[3].if.condition")).toBe("pruefe");
});

const withFallback = {
  schema_version: 1 as const,
  name: "f",
  steps: [
    { id: "a", tool: "ls", on_error: { action: "fallback" as const, steps: [{ id: "b", kind: "message" as const, text: "{{ a.stderr }}" }] } },
    { id: "c", kind: "if" as const, condition: { source: "a.stdout", is_empty: true }, then: [], else: [] },
  ],
};

test("removing the last fallback step drops on_error", () => {
  const r = removeStep(withFallback, "b").wf;
  expect(findStep(r, "a")?.step).not.toHaveProperty("on_error");
});

test("rename touches only references (empty else stays)", () => {
  const r = renameStep(withFallback, "a", "z").wf;
  expect(JSON.parse(JSON.stringify(r).replaceAll('"z"', '"a"').replaceAll("z.", "a."))).toEqual(withFallback);
  expect(findStep(r, "c")?.step).toHaveProperty("else", []);
});

test("rename keeps escaped literal braces but renames after an escaped backslash", () => {
  const w = { schema_version: 1 as const, name: "e", steps: [{ id: "a", tool: "ls" }, { id: "m", kind: "message" as const, text: "\\{{ a.x }} \\\\{{ a.y }} {{ a.z }}" }] };
  const text = (findStep(renameStep(w, "a", "q").wf, "m")?.step as { text: string }).text;
  expect(text).toBe("\\{{ a.x }} \\\\{{ q.y }} {{ q.z }}");
});

test("error paths into on_error.steps resolve to the fallback step", () => {
  expect(stepIdAtErrorPath(withFallback, "steps[0].command.on_error.steps[0].message.text")).toBe("b");
  expect(stepIdAtErrorPath(withFallback, "steps[0].command.tool")).toBe("a");
});

test("moveStep inside a one-step fallback keeps on_error.action", () => {
  const x = { id: "x", kind: "message" as const, text: "t" };
  const w: Workflow = {
    schema_version: 1, name: "n",
    steps: [{ id: "a", tool: "ls", on_error: { action: "fallback", steps: [x] } }],
  };
  expect(moveStep(w, "x", ["a", "fallback"], 0).wf).toEqual(w);
  expect(moveStep(w, "x", ["a", "fallback"]).wf).toEqual(w);
});
