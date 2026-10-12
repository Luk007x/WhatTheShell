// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { logErrors as wf } from "./fixture";
import { toGraph } from "./graph";

test("log_errors graph", () => {
  const { nodes, edges } = toGraph(wf);
  expect(nodes.map((n) => n.id)).toEqual(["finde", "suche", "zaehle", "pruefe", "bericht", "ok"]);
  const e = edges.map((x) => `${x.source}.${x.sourceHandle}->${x.target}.${x.targetHandle}`);
  expect(e).toEqual([
    "finde.next->suche.in",
    "suche.next->zaehle.in",
    "suche.stdout->zaehle.stdin",
    "zaehle.next->pruefe.in",
    "pruefe.then->bericht.in",
    "pruefe.else->ok.in",
  ]);
  expect(edges.find((x) => x.data?.kind === "pipe")?.style?.strokeDasharray).toBeDefined();
  expect(nodes.find((n) => n.id === "bericht")?.data.depth).toBe(1);
});

test("stored layout wins, others are placed", () => {
  const { nodes } = toGraph({ ...wf, layout: { nodes: { finde: { x: 5, y: 6 } } } });
  expect(nodes[0]?.position).toEqual({ x: 5, y: 6 });
  expect(Number.isFinite(nodes[1]?.position.y)).toBe(true);
  expect(nodes[1]?.position).not.toEqual({ x: 0, y: 0 });
});
