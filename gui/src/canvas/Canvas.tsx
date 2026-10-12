// SPDX-License-Identifier: AGPL-3.0-or-later
import "@xyflow/react/dist/style.css";
import {
  applyNodeChanges, Background, Controls, Handle, MiniMap, Position, ReactFlow,
  type Connection, type NodeChange, type NodeProps,
} from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";
import { t } from "../i18n";
import { commandStep, CONTROL_KINDS, controlStep } from "../model/blocks";
import { toGraph, type FlowEdge, type StepNode } from "../model/graph";
import {
  addStep, findStep, isCommand, moveAfter, moveStep, portsOf, removeStep, setLayout, updateStep,
  type OpResult, type Port, type Step,
} from "../model/ops";
import type { Workflow } from "../types/workflow";

export type Edit = (op: (wf: Workflow) => OpResult | Workflow, key?: string) => void;

const subtitle = (s: Step): string => {
  if (isCommand(s)) return [s.tool, ...(s.command ?? [])].join(" ");
  return t(`kind.${s.kind}`);
};

function StepNodeView({ data, selected }: NodeProps<StepNode>) {
  const s = data.step;
  const kind = s.kind ?? "command";
  const safety = data.safety ?? null;
  return (
    <div className={`node kind-${kind}${safety ? ` safety-${safety}` : ""}${selected ? " sel" : ""}`}>
      <Handle type="target" position={Position.Top} id="in" />
      {kind === "command" && <Handle type="target" position={Position.Left} id="stdin" title={t("stream.stdin")} />}
      <div className="node-title">{s.label ?? s.id}</div>
      <div className="node-sub">
        {subtitle(s)}
        {safety && <> · {t(`safety.${safety}`)}</>}
      </div>
      {kind === "if" && (
        <>
          <Handle type="source" position={Position.Right} id="then" style={{ top: "30%" }} title={t("port.then")} />
          <Handle type="source" position={Position.Right} id="else" style={{ top: "65%" }} title={t("port.else")} />
        </>
      )}
      {kind === "foreach" && <Handle type="source" position={Position.Right} id="body" title={t("port.body")} />}
      {kind === "command" && (
        <>
          <Handle type="source" position={Position.Right} id="stdout" style={{ top: "30%" }} title={t("stream.stdout")} />
          <Handle type="source" position={Position.Right} id="fallback" style={{ top: "70%" }} title={t("port.fallback")} />
        </>
      )}
      <Handle type="source" position={Position.Bottom} id="next" title={t("port.next")} />
    </div>
  );
}

const nodeTypes = { step: StepNodeView };
const SOURCE_PORTS = ["next", "then", "else", "body", "fallback", "stdout"];

export function Canvas(props: {
  wf: Workflow;
  selected: string | null;
  onSelect: (id: string | null) => void;
  edit: Edit;
  catalogTool: string | null;
  safetyOf: (tool: string) => string | null;
}) {
  const { wf, selected, onSelect, edit, catalogTool, safetyOf } = props;
  const [hint, setHint] = useState<string | null>(null);
  const [target, setTarget] = useState("end");
  const graph = useMemo(() => toGraph(wf), [wf]);
  const [nodes, setNodes] = useState<StepNode[]>(graph.nodes);

  useEffect(() => {
    setNodes(graph.nodes.map((n) => ({
      ...n,
      selected: n.id === selected,
      data: { ...n.data, safety: isCommand(n.data.step) ? safetyOf(n.data.step.tool) : null },
    })));
  }, [graph, selected, safetyOf]);

  const onNodesChange = (changes: NodeChange<StepNode>[]) =>
    setNodes((ns) => applyNodeChanges(changes.filter((c) => c.type !== "remove"), ns)); // removal goes through the document

  const onConnect = (c: Connection) => {
    const { source, target, sourceHandle: port } = c;
    if (source === target || !port) return;
    if (port === "next") edit((w) => moveAfter(w, target, source));
    else if (port === "stdout") edit((w) => updateStep(w, target, { stdin: { pipe: source } }));
    else edit((w) => moveStep(w, target, [source, port], 0));
  };

  const isValidConnection = (c: { sourceHandle?: string | null; targetHandle?: string | null }) =>
    c.sourceHandle === "stdout" ? c.targetHandle === "stdin" : SOURCE_PORTS.includes(c.sourceHandle ?? "") && c.targetHandle === "in";

  const selHit = selected ? findStep(wf, selected) : undefined;
  const targets = selHit ? portsOf(selHit.step).filter((p): p is Exclude<Port, "fallback"> => p !== "fallback") : [];
  const path = selected && targets.some((p) => p === target) ? [selected, target] : [];
  const add = (step: Step) => { edit((w) => addStep(w, step, path)); onSelect(step.id); };
  return (
    <section className="panel canvas" aria-labelledby="canvas-h">
      <h2 id="canvas-h" className="sr-only">{t("canvas.title")}</h2>
      <div className="toolbar" role="toolbar" aria-label={t("canvas.toolbar")}>
        <label>
          {t("canvas.name")} <input value={wf.name} onChange={(e) => edit((w) => ({ ...w, name: e.target.value }), "name")} />
        </label>
        {targets.length > 0 && (
          <label>
            {t("canvas.target")}{" "}
            <select value={path.length ? target : "end"} onChange={(e) => setTarget(e.target.value)}>
              <option value="end">{t("canvas.target.end")}</option>
              {targets.map((p) => <option key={p} value={p}>{t(`canvas.target.${p}`)}</option>)}
            </select>
          </label>
        )}
        <button disabled={!catalogTool} onClick={() => catalogTool && add(commandStep(wf, catalogTool))}>
          {catalogTool ? t("canvas.add.tool", { name: catalogTool }) : t("canvas.add.pick")}
        </button>
        {CONTROL_KINDS.map((k) => (
          <button key={k} onClick={() => add(controlStep(wf, k))}>{t(`kind.${k}`)}</button>
        ))}
        <button disabled={!selected} onClick={() => selected && edit((w) => removeStep(w, selected))}>{t("canvas.delete")}</button>
      </div>
      {hint && <p role="status" className="hint">{hint}</p>}
      <div className="flow">
        <ReactFlow<StepNode, FlowEdge>
          nodes={nodes}
          edges={graph.edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onConnect={onConnect}
          isValidConnection={isValidConnection}
          onNodeClick={(_, n) => { setHint(null); onSelect(n.id); }}
          onPaneClick={() => { setHint(null); onSelect(null); }}
          onNodeDragStop={(_, n) => edit((w) => setLayout(w, n.id, n.position))}
          onDelete={({ nodes: ns, edges: es }) => {
            const gone = new Set(ns.map((n) => n.id));
            if (ns.length > 0) edit((w) => ns.reduce<OpResult>((r, n) => removeStep(r.wf, n.id), { wf: w, warnings: [] }));
            for (const e of es) {
              if (gone.has(e.source) || gone.has(e.target)) continue; // edges of deleted nodes vanish silently
              if (e.data?.kind === "pipe") edit((w) => updateStep(w, e.target, { stdin: undefined }));
              else setHint(t("canvas.flowHint"));
            }
          }}
          nodesFocusable
          fitView
        >
          <Background />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </div>
    </section>
  );
}
