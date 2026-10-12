// SPDX-License-Identifier: AGPL-3.0-or-later
// Derives the React Flow graph from the workflow document. Never stored (F-33).
// Ports by step kind (D-012): every step `in` (target, top) and `next` (source, bottom); if: `then`/`else`; foreach: `body`;
// on_error.action fallback: `fallback`; only command: `stdin` (target, left) and `stdout` (source, right).
import dagre from "@dagrejs/dagre";
import { MarkerType, type Edge, type Node } from "@xyflow/react";
import type { Workflow } from "../types/workflow";
import { childSeq, isCommand, portsOf, visibleSteps, type Port, type SeqPath, type Step } from "./ops";

export interface StepNodeData extends Record<string, unknown> {
  step: Step;
  path: SeqPath;
  depth: number;
  /** Safety class of the tool, filled in by the canvas from the catalog. */
  safety?: string | null;
  /** Catalog category of the tool, filled in by the canvas. */
  category?: string | null;
}
export type StepNode = Node<StepNodeData, "step">;
/** `port` is the source handle of a flow edge (`next` or a branch port). */
export type FlowEdge = Edge<{ kind: "flow" | "pipe"; port?: string }>;

export type HandleId = "in" | "next" | Port | "stdin" | "stdout";
export interface HandleSpec {
  id: HandleId;
  type: "source" | "target";
  side: "top" | "bottom" | "left" | "right";
  /** flow = order of steps, data = recorded stdout as stdin of a later command. */
  kind: "flow" | "data";
  /** Horizontal position in percent for bottom handles. */
  x?: number;
}

export const NODE_W = 220;
export const NODE_H = 96;

/** The handles a step offers, nothing else (D-012). */
export function handlesOf(step: Step): HandleSpec[] {
  const out: HandleSpec[] = [{ id: "in", type: "target", side: "top", kind: "flow" }];
  if (isCommand(step)) out.push({ id: "stdin", type: "target", side: "left", kind: "data" }, { id: "stdout", type: "source", side: "right", kind: "data" });
  const kind = step.kind ?? "command";
  const branches: Port[] =
    kind === "if" ? ["then", "else"] : kind === "foreach" ? ["body"] : isCommand(step) && (step.on_error?.action === "fallback" || step.on_error?.steps) ? ["fallback"] : []; // steps without the action would otherwise leave an edge without handle
  // `next` in the middle, then/body left, else/fallback right
  const x: Record<Port, number> = { then: 18, body: 18, else: 82, fallback: 82 };
  out.push({ id: "next", type: "source", side: "bottom", kind: "flow", x: 50 });
  for (const p of branches) out.push({ id: p, type: "source", side: "bottom", kind: "flow", x: x[p] });
  return out;
}

/** Which edge a handle pair makes: stdout → stdin is data, every flow source → in is order. Anything else is refused. */
export function connectionKind(sourceHandle: string | null | undefined, targetHandle: string | null | undefined): "flow" | "pipe" | null {
  if (sourceHandle === "stdout") return targetHandle === "stdin" ? "pipe" : null;
  const flowSources: (string | null | undefined)[] = ["next", "then", "else", "body", "fallback"];
  return flowSources.includes(sourceHandle) && targetHandle === "in" ? "flow" : null;
}

export type ConnectRefusal = "self" | "kind" | "backpipe";
type Link = { source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null };

/** Why a drag between two handles is refused (checked before the drop), or null if it is fine. */
export function connectionProblem(wf: Workflow, c: Link): ConnectRefusal | null {
  if (c.source === c.target) return "self";
  const kind = connectionKind(c.sourceHandle, c.targetHandle);
  if (kind === null) return "kind";
  if (kind === "pipe" && !visibleSteps(wf, c.target).includes(c.source)) return "backpipe"; // the target would read a step that has not run
  return null;
}

export function toGraph(wf: Workflow): { nodes: StepNode[]; edges: FlowEdge[] } {
  const nodes: StepNode[] = [];
  const edges: FlowEdge[] = [];
  const flow = (source: string, sourceHandle: string, target: string): FlowEdge => ({
    id: `flow:${source}.${sourceHandle}->${target}`,
    source,
    sourceHandle,
    target,
    targetHandle: "in",
    className: "edge-flow",
    markerEnd: { type: MarkerType.ArrowClosed, color: "var(--edge-flow)" },
    data: { kind: "flow", port: sourceHandle },
  });
  const walk = (steps: Step[], path: SeqPath) => {
    steps.forEach((step, i) => {
      nodes.push({ id: step.id, type: "step", position: { x: 0, y: 0 }, data: { step, path, depth: path.length / 2 } });
      const prev = steps[i - 1];
      if (prev) edges.push(flow(prev.id, "next", step.id));
      if (isCommand(step) && step.stdin?.pipe) {
        edges.push({
          id: `pipe:${step.stdin.pipe}->${step.id}`,
          source: step.stdin.pipe,
          sourceHandle: "stdout",
          target: step.id,
          targetHandle: "stdin",
          className: "edge-pipe",
          markerEnd: { type: MarkerType.ArrowClosed, color: "var(--edge-data)" },
          data: { kind: "pipe" },
          style: { strokeDasharray: "6 4" },
        });
      }
      for (const port of portsOf(step)) {
        const sub = childSeq(step, port) ?? [];
        const first = sub[0];
        if (first) edges.push(flow(step.id, port, first.id));
        walk(sub, [...path, step.id, port]);
      }
    });
  };
  walk(wf.steps, []);

  // Auto layout only for nodes without a stored position. ponytail: unlaid nodes may shift when the structure changes, write layout on drag
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 70 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) g.setNode(n.id, { width: NODE_W, height: NODE_H });
  for (const e of edges) if (e.data?.kind === "flow") g.setEdge(e.source, e.target);
  dagre.layout(g);
  const stored = wf.layout?.nodes ?? {};
  for (const n of nodes) {
    const p = stored[n.id];
    const d = g.node(n.id);
    n.position = p ? { x: p.x, y: p.y } : { x: d.x - NODE_W / 2, y: d.y - NODE_H / 2 };
  }
  return { nodes, edges };
}
