// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { canDrop, dropIndex, moveTargets, toBlocks, type Block, type Move } from "./blocks";
import { logErrors as wf } from "./fixture";
import { allSteps, moveStep } from "./ops";

const flat = (bs: Block[]): Block[] => bs.flatMap((b) => [b, ...b.slots.flatMap((s) => flat(s.blocks))]);
const ids = (bs: Block[]) => bs.map((b) => b.step.id);

test("log_errors blocks: 4 root blocks (6 steps in total), if with named slots", () => {
  const blocks = toBlocks(wf);
  expect(ids(blocks)).toEqual(["finde", "suche", "zaehle", "pruefe"]);
  expect(ids(flat(blocks))).toEqual(allSteps(wf.steps).map((s) => s.id));
  const slots = blocks[3]?.slots ?? [];
  expect(slots.map((s) => [s.port, ids(s.blocks)])).toEqual([["then", ["bericht"]], ["else", ["ok"]]]);
  expect(slots[1]?.path).toEqual(["pruefe", "else"]);
});

test("empty slots stay visible", () => {
  const empty = { ...wf, steps: [{ id: "a", kind: "foreach" as const, source: "x", body: [] }] };
  expect(toBlocks(empty)[0]?.slots).toEqual([{ port: "body", path: ["a", "body"], blocks: [] }]);
});

test("round trip through ops leaves the document unchanged", () => {
  let cur = wf;
  for (const b of flat(toBlocks(wf))) cur = moveStep(cur, b.step.id, b.path, b.index).wf;
  expect(cur).toEqual(wf);
});

const apply = (id: string, m: Move | null) => {
  if (!m) throw new Error("no move");
  return moveStep(wf, id, m.path, m.index).wf;
};

test("keyboard moves equal moveStep calls", () => {
  expect(apply("suche", moveTargets(wf, "suche").up)).toEqual(moveStep(wf, "suche", [], 0).wf);
  expect(apply("suche", moveTargets(wf, "suche").down)).toEqual(moveStep(wf, "suche", [], 2).wf);
  expect(apply("ok", moveTargets(wf, "ok").out)).toEqual(moveStep(wf, "ok", [], 4).wf);
  expect(moveTargets(wf, "finde").up).toBeNull();
  expect(moveTargets(wf, "ok").down).toBeNull();
  expect(moveTargets(wf, "finde").out).toBeNull();
});

test("into goes to the slots of the preceding container", () => {
  const w = moveStep(wf, "ok", [], 4).wf; // ok now behind pruefe
  const into = moveTargets(w, "ok").into;
  expect(into.map((i) => i.path)).toEqual([["pruefe", "then"], ["pruefe", "else"]]);
  expect(moveStep(w, "ok", ["pruefe", "else"]).wf).toEqual(wf);
  expect(moveTargets(wf, "finde").into).toEqual([]);
});

test("drop rules", () => {
  expect(canDrop(["pruefe", "then"], "pruefe")).toBe(false);
  expect(canDrop(["pruefe", "then"], "suche")).toBe(true);
  expect(dropIndex(wf, "suche", [], 3)).toBe(2); // zone behind zaehle, step taken out first
  expect(dropIndex(wf, "suche", [], 0)).toBe(0);
  expect(dropIndex(wf, "ok", [], 4)).toBe(4);
});
