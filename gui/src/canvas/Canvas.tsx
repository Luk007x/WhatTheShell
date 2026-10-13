// SPDX-License-Identifier: AGPL-3.0-or-later
import "@xyflow/react/dist/style.css";
import {
  applyNodeChanges, Background, Controls, Handle, MiniMap, Panel, Position, ReactFlow, useReactFlow,
  type Connection, type NodeChange, type NodeProps, type OnConnectEnd, type ReactFlowInstance,
} from "@xyflow/react";
import { Fragment, useEffect, useMemo, useRef, useState, type DragEvent, type MutableRefObject } from "react";
import { categoryClass } from "../catalog/groupTools";
import { t } from "../i18n";
import type { Theme } from "../theme";
import { Icon } from "../icons";
import { Modal } from "../Modal";
import { commandStep, CONTROL_KINDS, controlStep, MIME_KIND, MIME_TOOL } from "../model/blocks";
import { connectionKind, connectionProblem, handlesOf, toGraph, type FlowEdge, type HandleSpec, type StepNode } from "../model/graph";
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

/** Colour class of a node or block head: tool category for commands, fixed colours for control and helper steps. */
export const headClass = (s: Step, category: string | null | undefined): string =>
  isCommand(s) ? categoryClass(category) : s.kind === "if" || s.kind === "foreach" ? "cat-control" : "cat-misc";

const POSITION = { top: Position.Top, bottom: Position.Bottom, left: Position.Left, right: Position.Right } as const;

function Port({ h, index }: { h: HandleSpec; index: number }) {
  const full = t(`port.${h.id}`);
  const x = h.x !== undefined ? `${h.x}%` : undefined;
  return (
    <>
      <Handle type={h.type} position={POSITION[h.side]} id={h.id} className={`port port-${h.kind}`} style={x ? { left: x } : undefined}
        title={full} aria-label={full} role="img" />
      <span className={`port-label port-label-${h.side}`} style={{ left: x }} title={full} aria-hidden="true">
        {t(`port.${h.id}.short`)}
        {/* stacked below each other so several full labels never overlap */}
        <span className="port-full" style={h.side === "bottom" ? { top: `calc(100% + ${0.25 + index * 1.75}rem)` } : undefined}>{full}</span>
      </span>
    </>
  );
}

function StepNodeView({ data, selected }: NodeProps<StepNode>) {
  const s = data.step;
  const kind = s.kind ?? "command";
  const safety = data.safety ?? null;
  const hs = handlesOf(s);
  const at = (side: HandleSpec["side"]) => hs.filter((h) => h.side === side).map((h, i) => <Port key={h.id} h={h} index={i} />);
  return (
    <div className={`node kind-${kind}${selected ? " sel" : ""}`}>
      {at("top")}
      <div className={`node-head ${headClass(s, data.category)}`}>
        <span className="node-title">{s.label ?? s.id}</span>
        {safety && <span className={`badge badge--${safety}`}>{t(`safety.${safety}`)}</span>}
      </div>
      <div className="node-sub" title={subtitle(s)}>{subtitle(s)}</div>
      {kind === "command" && <div className="node-io">{at("left")}{at("right")}</div>}
      <div className="node-out">{at("bottom")}</div>
    </div>
  );
}

const nodeTypes = { step: StepNodeView };
const FIT = { maxZoom: 1, padding: 0.15 };

/** Keep every node in sight when steps are added or removed (the pane itself never scrolls). */
function AutoFit({ count }: { count: number }) {
  const { fitView } = useReactFlow();
  useEffect(() => { void fitView(FIT); }, [count, fitView]);
  return null;
}

/** "?" button with the explanation of what flows along the edges (D-012). */
export function FlowHelp() {
  const [open, setOpen] = useState(false);
  const title = t("help.flow.title");
  return (
    <>
      <button className="btn--icon" aria-label={title} title={title} onClick={() => setOpen(true)}><Icon name="help" /></button>
      <Modal open={open} title={title} onCancel={() => setOpen(false)}>
        {/* backticks in the text mark code */}
        <p className="help-text">{t("help.flow.text").split("`").map((part, i) => (i % 2 ? <code key={i}>{part}</code> : <Fragment key={i}>{part}</Fragment>))}</p>
        <div className="actions"><button data-autofocus onClick={() => setOpen(false)}>{t("settings.close")}</button></div>
      </Modal>
    </>
  );
}

function Legend() {
  return (
    <details className="legend">
      <summary>{t("legend.title")}</summary>
      <ul>
        <li><svg width="36" height="10" aria-hidden="true"><path d="M2 5h26" className="lg-flow" /><path d="M27 1l7 4-7 4z" className="lg-flow-head" /></svg> {t("legend.flow")}</li>
        <li><svg width="36" height="10" aria-hidden="true"><path d="M2 5h26" className="lg-data" /><path d="M27 1l7 4-7 4z" className="lg-data-head" /></svg> {t("legend.data")}</li>
      </ul>
      <h3>{t("legend.ports")}</h3>
      <ul>
        {(["in", "next", "then", "else", "body", "fallback", "stdin", "stdout"] as const).map((p) => (
          <li key={p}><span className={`lg-port port-${p === "stdin" || p === "stdout" ? "data" : "flow"}`} aria-hidden="true" /> <strong>{t(`port.${p}.short`)}</strong> {t(`port.${p}`)}</li>
        ))}
      </ul>
      <h3>{t("legend.safety")}</h3>
      <p className="lg-badges">{(["safe", "caution", "dangerous"] as const).map((s) => <span key={s} className={`badge badge--${s}`}>{t(`safety.${s}`)}</span>)}</p>
      <p className="muted">{t("legend.category")}</p>
    </details>
  );
}

export function Canvas(props: {
  wf: Workflow;
  selected: string | null;
  onSelect: (id: string | null) => void;
  edit: Edit;
  catalogTool: string | null;
  safetyOf: (tool: string) => string | null;
  categoryOf: (tool: string) => string | null;
  /** Short message for the status line; null clears it. */
  onNotice: (text: string | null) => void;
  theme: Theme;
  /** Names of known catalog tools; a dropped name outside it is ignored. */
  knownTools: ReadonlySet<string>;
  /** Set to "append this tool at the chosen target" for the catalog's Enter key. */
  addToolRef?: MutableRefObject<((tool: string) => void) | null>;
}) {
  const { wf, selected, onSelect, edit, catalogTool, safetyOf, categoryOf, onNotice, addToolRef, knownTools } = props;
  const rf = useRef<ReactFlowInstance<StepNode, FlowEdge> | null>(null);
  const [target, setTarget] = useState("end");
  const graph = useMemo(() => toGraph(wf), [wf]);
  const [nodes, setNodes] = useState<StepNode[]>(graph.nodes);

  useEffect(() => {
    setNodes(graph.nodes.map((n) => {
      const s = n.data.step;
      const safety = isCommand(s) ? safetyOf(s.tool) : null;
      return {
        ...n,
        selected: n.id === selected,
        ariaLabel: [s.label ?? s.id, t(`kind.${s.kind ?? "command"}`), safety ? t(`safety.${safety}`) : ""].filter(Boolean).join(", "),
        data: { ...n.data, safety, category: isCommand(s) ? categoryOf(s.tool) : null },
      };
    }));
  }, [graph, selected, safetyOf, categoryOf]);

  const edges: FlowEdge[] = graph.edges.map((e) => {
    const pipe = e.data?.kind === "pipe";
    const port = e.data?.port;
    return {
      ...e,
      label: pipe ? t("edge.pipe") : port && port !== "next" ? t(`port.${port}.short`) : undefined,
      labelBgPadding: [4, 2],
      labelBgBorderRadius: 4,
      ariaLabel: t(pipe ? "edge.pipe.aria" : "edge.flow.aria", { a: e.source, b: e.target }),
    };
  });

  const onNodesChange = (changes: NodeChange<StepNode>[]) =>
    setNodes((ns) => applyNodeChanges(changes.filter((c) => c.type !== "remove"), ns)); // removal goes through the document

  const onConnect = (c: Connection) => {
    const { source, target, sourceHandle: port } = c;
    const kind = connectionKind(port, c.targetHandle);
    const problem = connectionProblem(wf, c);
    if (problem || !port || !kind) { onNotice(t(`connect.${problem ?? "kind"}`)); return; }
    onNotice(null);
    if (kind === "pipe") edit((w) => updateStep(w, target, { stdin: { pipe: source } }));
    else if (port === "next") edit((w) => moveAfter(w, target, source));
    else edit((w) => moveStep(w, target, [source, port], 0));
  };
  // a drop on a handle that does not fit never reaches onConnect: say why
  const onConnectEnd: OnConnectEnd = (_, state) => {
    const { fromHandle: from, toHandle: to } = state;
    if (!from || !to || state.isValid) return;
    const [a, b] = from.type === "source" ? [from, to] : [to, from]; // a drag may start at the target handle
    const problem = connectionProblem(wf, { source: a.nodeId, sourceHandle: a.id, target: b.nodeId, targetHandle: b.id });
    onNotice(t(`connect.${problem ?? "kind"}`));
  };

  const isValidConnection = (c: { source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null }) => connectionProblem(wf, c) === null;

  const selHit = selected ? findStep(wf, selected) : undefined;
  const targets = selHit ? portsOf(selHit.step).filter((p): p is Exclude<Port, "fallback"> => p !== "fallback") : [];
  const path = selected && targets.some((p) => p === target) ? [selected, target] : [];
  const add = (step: Step) => { edit((w) => addStep(w, step, path)); onSelect(step.id); };
  useEffect(() => {
    if (!addToolRef) return;
    addToolRef.current = (name) => add(commandStep(wf, name));
    return () => { addToolRef.current = null; };
  }); // every render: `add` closes over the current document and target
  const dragStart = (type: string, value: string) => (e: DragEvent) => { e.dataTransfer.setData(type, value); e.dataTransfer.effectAllowed = "copy"; };
  const onDrop = (e: DragEvent) => {
    e.preventDefault(); // also for foreign drops (files): the browser must not navigate away
    const name = e.dataTransfer.getData(MIME_TOOL);
    const kind = CONTROL_KINDS.find((k) => k === e.dataTransfer.getData(MIME_KIND)); // untrusted string: only known kinds
    const pos = rf.current?.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    if (!pos) return;
    if (name ? !knownTools.has(name) : !kind) return; // unknown names may come from another tab: ignore
    const step = name ? commandStep(wf, name) : controlStep(wf, kind ?? "message"); // `kind` is set when `name` is empty
    edit((w) => { const r = addStep(w, step, path); return r.wf === w ? r : { ...r, wf: setLayout(r.wf, step.id, pos) }; });
    onSelect(step.id);
  };
  return (
    <section className="panel canvas" aria-labelledby="canvas-h">
      <h2 id="canvas-h" className="sr-only">{t("canvas.title")}</h2>
      <div className="toolbar" role="toolbar" aria-label={t("canvas.toolbar")}>
        <label className="tb-field">
          {t("canvas.name")} <input value={wf.name} onChange={(e) => edit((w) => ({ ...w, name: e.target.value }), "name")} />
        </label>
        {targets.length > 0 && (
          <label className="tb-field">
            {t("canvas.target")}{" "}
            <select value={path.length ? target : "end"} onChange={(e) => setTarget(e.target.value)}>
              <option value="end">{t("canvas.target.end")}</option>
              {targets.map((p) => <option key={p} value={p}>{t(`canvas.target.${p}`)}</option>)}
            </select>
          </label>
        )}
        <span className="tb-group">
          <button className="btn--primary" disabled={!catalogTool} onClick={() => catalogTool && add(commandStep(wf, catalogTool))}>
            <Icon name="plus" />{catalogTool ? t("canvas.add.tool", { name: catalogTool }) : t("canvas.add.pick")}
          </button>
          {CONTROL_KINDS.map((k) => (
            <button key={k} draggable onDragStart={dragStart(MIME_KIND, k)} onClick={() => add(controlStep(wf, k))}>{t(`kind.${k}`)}</button>
          ))}
        </span>
        <button className="btn--danger" disabled={!selected} onClick={() => selected && edit((w) => removeStep(w, selected))}><Icon name="trash" />{t("canvas.delete")}</button>
        <span className="tb-spacer" />
        <FlowHelp />
      </div>
      <div className="flow">
        <ReactFlow<StepNode, FlowEdge>
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          colorMode={props.theme}
          onInit={(i) => { rf.current = i; }}
          onDragOver={(e) => { if (e.dataTransfer.types.some((x) => x === MIME_TOOL || x === MIME_KIND)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; } }}
          onDrop={onDrop}
          deleteKeyCode={["Delete", "Backspace"]}
          onNodesChange={onNodesChange}
          onConnect={onConnect}
          onConnectEnd={onConnectEnd}
          isValidConnection={isValidConnection}
          onNodeClick={(_, n) => { onNotice(null); onSelect(n.id); }}
          onPaneClick={() => { onNotice(null); onSelect(null); }}
          onNodeDragStop={(_, n) => edit((w) => setLayout(w, n.id, n.position))}
          onDelete={({ nodes: ns, edges: es }) => {
            const gone = new Set(ns.map((n) => n.id));
            if (selected && gone.has(selected)) onSelect(null);
            if (ns.length > 0) edit((w) => ns.reduce<OpResult>((r, n) => removeStep(r.wf, n.id), { wf: w, warnings: [] }));
            for (const e of es) {
              if (gone.has(e.source) || gone.has(e.target)) continue; // edges of deleted nodes vanish silently
              if (e.data?.kind === "pipe") edit((w) => updateStep(w, e.target, { stdin: undefined }));
              else onNotice(t("canvas.flowHint"));
            }
          }}
          nodesFocusable
          fitView
          fitViewOptions={FIT}
          minZoom={0.2}
        >
          <AutoFit count={nodes.length} />
          <Background />
          <Controls />
          <MiniMap pannable zoomable />
          <Panel position="top-right"><Legend /></Panel>
        </ReactFlow>
      </div>
    </section>
  );
}
