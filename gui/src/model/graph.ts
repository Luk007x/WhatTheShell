// SPDX-License-Identifier: AGPL-3.0-or-later
// Derives the React Flow graph from the workflow document. Never stored (F-33).
// Ports: all steps `in` (target) and `next` (source); if: `then`/`else`; foreach: `body`;
// command: `fallback` (when on_error.steps exist), `stdout` (source), `stdin` (target).
import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";
import type { Workflow } from "../types/workflow";
import { childSeq, isCommand, portsOf, type SeqPath, type Step } from "./ops";

export interface StepNodeData extends Record<string, unknown> {
  step: Step;
  path: SeqPath;
  depth: number;
  /** Safety class of the tool, filled in by the canvas from the catalog. */
  safety?: string | null;
}
export type StepNode = Node<StepNodeData, "step">;
export type FlowEdge = Edge<{ kind: "flow" | "pipe" }>;

export const NODE_W = 200;
export const NODE_H = 64;

export function toGraph(wf: Workflow): { nodes: StepNode[]; edges: FlowEdge[] } {
  const nodes: StepNode[] = [];
  const edges: FlowEdge[] = [];
  const flow = (source: string, sourceHandle: string, target: string): FlowEdge => ({
    id: `flow:${source}.${sourceHandle}->${target}`,
    source,
    sourceHandle,
    target,
    targetHandle: "in",
    data: { kind: "flow" },
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
  g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 50 });
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
