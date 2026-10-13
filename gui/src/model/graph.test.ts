// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { logErrors as wf } from "./fixture";
import { connectionKind, connectionProblem, handlesOf, toGraph } from "./graph";

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

const ids = (s: Parameters<typeof handlesOf>[0]) => handlesOf(s).map((h) => `${h.id}:${h.type}`).sort();

test("handles by step kind", () => {
  expect(ids({ id: "a", tool: "ls" })).toEqual(["in:target", "next:source", "stdin:target", "stdout:source"]);
  expect(ids({ id: "a", tool: "ls", on_error: { action: "fallback", steps: [] } })).toEqual(
    ["fallback:source", "in:target", "next:source", "stdin:target", "stdout:source"]);
  expect(ids({ id: "a", tool: "ls", on_error: { action: "retry", retries: 2 } })).not.toContain("fallback:source");
  expect(ids({ id: "a", kind: "if", condition: { source: "x.stdout", is_empty: true }, then: [] })).toEqual(
    ["else:source", "in:target", "next:source", "then:source"]);
  expect(ids({ id: "a", kind: "foreach", source: "x.stdout", body: [] })).toEqual(["body:source", "in:target", "next:source"]);
  for (const s of [
    { id: "a", kind: "set" as const, variable: "v", value: "1" },
    { id: "a", kind: "wait" as const, seconds: 1 },
    { id: "a", kind: "message" as const, text: "x" },
    { id: "a", kind: "abort" as const },
  ]) expect(ids(s)).toEqual(["in:target", "next:source"]);
});

test("only stdout → stdin and flow → in connect", () => {
  expect(connectionKind("stdout", "stdin")).toBe("pipe");
  expect(connectionKind("next", "in")).toBe("flow");
  expect(connectionKind("then", "in")).toBe("flow");
  expect(connectionKind("stdout", "in")).toBeNull();
  expect(connectionKind("next", "stdin")).toBeNull();
  expect(connectionKind(null, "in")).toBeNull();
});

test("edges carry kind, arrow and port", () => {
  const { edges } = toGraph(wf);
  const flowEdge = edges.find((x) => x.id === "flow:pruefe.then->bericht");
  expect(flowEdge?.data).toEqual({ kind: "flow", port: "then" });
  expect(flowEdge?.markerEnd).toBeDefined();
  expect(edges.find((x) => x.data?.kind === "pipe")?.className).toBe("edge-pipe");
});

test("connectionProblem: self, wrong ports, backward pipe", () => {
  expect(connectionProblem(wf, { source: "suche", target: "suche", sourceHandle: "stdout", targetHandle: "stdin" })).toBe("self");
  expect(connectionProblem(wf, { source: "suche", target: "zaehle", sourceHandle: "stdout", targetHandle: "in" })).toBe("kind");
  expect(connectionProblem(wf, { source: "zaehle", target: "suche", sourceHandle: "stdout", targetHandle: "stdin" })).toBe("backpipe");
  expect(connectionProblem(wf, { source: "finde", target: "zaehle", sourceHandle: "stdout", targetHandle: "stdin" })).toBeNull();
  expect(connectionProblem(wf, { source: "zaehle", target: "finde", sourceHandle: "next", targetHandle: "in" })).toBeNull();
});

test("terminal step: flow ports only, no stdin/stdout", () => {
  expect(ids({ id: "a", kind: "terminal", tool: "vim" })).toEqual(["in:target", "next:source"]);
});
