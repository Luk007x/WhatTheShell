// SPDX-License-Identifier: AGPL-3.0-or-later
// Block view (D-010): the same step tree as nested, stackable cards. Pure presentation; every change is an op from model/ops.ts.
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { headClass, type Edit } from "../canvas/Canvas";
import { HelpButton } from "../Help";
import { Icon } from "../icons";
import { t } from "../i18n";
import { canDrop, commandStep, CONTROL_KINDS, controlStep, dropIndex, MIME_KIND, MIME_TOOL, moveTargets, placeOf, placeOfPath, toBlocks, type Block, type Move } from "../model/blocks";
import { addStep, isCommand, isToolStep, moveStep, removeStep, type SeqPath, type Step } from "../model/ops";
import { conditionOperator } from "../model/form";
import type { Workflow } from "../types/workflow";


const subtitle = (s: Step): string => {
  switch (s.kind) {
    case undefined:
    case "command":
    case "terminal": return [s.tool, ...(s.command ?? [])].join(" ");
    case "if": {
      const op = conditionOperator(s.condition);
      return [s.condition.source, op, op ? String(Reflect.get(s.condition, op)) : ""].join(" ").trim();
    }
    case "foreach": return s.source;
    case "set": return `${s.variable} = ${s.value}`;
    case "wait": return `${s.seconds} s`;
    case "message": return s.text;
    case "abort": return s.text ?? "";
  }
};

export function BlockView(props: {
  wf: Workflow;
  selected: string | null;
  onSelect: (id: string | null) => void;
  edit: Edit;
  catalogTool: string | null;
  safetyOf: (tool: string) => string | null;
  categoryOf: (tool: string) => string | null;
  knownTools: ReadonlySet<string>;
  interactiveTools: ReadonlySet<string>;
}) {
  const { wf, selected, onSelect, edit, catalogTool, safetyOf, categoryOf, knownTools, interactiveTools } = props;
  const toolStep = (name: string) => commandStep(wf, name, { terminal: interactiveTools.has(name) });
  const tree = useMemo(() => toBlocks(wf), [wf]);
  const [live, setLive] = useState("");
  const [menu, setMenu] = useState<string | null>(null);
  const [adding, setAdding] = useState<string | null>(null);
  const [drag, setDrag] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const refocus = useRef<string | null>(null);

  // blocks remount when they change parent: give the keyboard focus back to the moved block
  useEffect(() => {
    if (refocus.current) document.getElementById(`blk-${refocus.current}`)?.focus();
    refocus.current = null;
  }, [wf]);

  const move = (id: string, m: Move | null) => {
    if (!m) return;
    const r = moveStep(wf, id, m.path, m.index);
    if (JSON.stringify(r.wf) === JSON.stringify(wf)) return; // refused or no-op: no undo entry
    refocus.current = id;
    edit((w) => moveStep(w, id, m.path, m.index));
    setLive(t("blocks.moved", { id, to: placeOf(r.wf, id) }));
  };
  const remove = (id: string) => {
    edit((w) => removeStep(w, id));
    if (selected === id) onSelect(null);
  };
  const insert = (step: Step, path: SeqPath, index?: number) => {
    edit((w) => addStep(w, step, path, index));
    onSelect(step.id);
    setAdding(null);
    setLive(t("blocks.added", { id: step.id, where: placeOfPath(wf, path) }));
  };

  const zone = (path: SeqPath, index: number, tail: boolean, empty: boolean) => {
    const key = `${path.join("/")}#${index}`;
    const where = placeOfPath(wf, path);
    return (
      <li
        key={`zone:${key}`}
        className={`zone${tail ? " tail" : ""}${over === key ? " over" : ""}`}
        onDragOver={(e) => {
          if (e.dataTransfer.types.some((x) => x === MIME_TOOL || x === MIME_KIND)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setOver(key); }
          else if (drag && canDrop(path, drag)) { e.preventDefault(); setOver(key); }
        }}
        onDragLeave={() => setOver(null)}
        onDrop={(e) => {
          e.preventDefault();
          const name = e.dataTransfer.getData(MIME_TOOL);
          const kind = CONTROL_KINDS.find((k) => k === e.dataTransfer.getData(MIME_KIND)); // untrusted string: only known kinds
          if (name && knownTools.has(name)) insert(toolStep(name), path, index);
          else if (!name && kind) insert(controlStep(wf, kind), path, index);
          else if (drag && canDrop(path, drag)) move(drag, { path, index: dropIndex(wf, drag, path, index) });
          setOver(null);
          setDrag(null);
        }}
      >
        {empty && <span className="muted">{t("blocks.empty")}</span>}
        {tail && (
          <>
            <button aria-label={t("blocks.add", { where })} aria-expanded={adding === key} className="btn--icon" onClick={() => setAdding(adding === key ? null : key)}><Icon name="plus" /></button>
            {adding === key && (
              <ul className="add-list" aria-label={t("blocks.add", { where })}>
                <li>
                  <button disabled={!catalogTool} onClick={() => catalogTool && insert(toolStep(catalogTool), path)}>
                    {catalogTool ? t("blocks.add.tool", { name: catalogTool }) : t("canvas.add.pick")}
                  </button>
                </li>
                {CONTROL_KINDS.map((k) => <li key={k}><button onClick={() => insert(controlStep(wf, k), path)}>{t(`kind.${k}`)}</button></li>)}
              </ul>
            )}
          </>
        )}
      </li>
    );
  };

  const seq = (blocks: Block[], path: SeqPath, root = false) => (
    <ol className={`seq${root ? " root" : ""}${drag ? " dragging" : ""}`}>
      {blocks.map((b) => <Fragment key={b.step.id}>{zone(path, b.index, false, false)}{block(b)}</Fragment>)}
      {zone(path, blocks.length, true, blocks.length === 0)}
    </ol>
  );

  const block = (b: Block) => {
    const s = b.step;
    const kind = s.kind ?? "command";
    const safety = isToolStep(s) ? safetyOf(s.tool) : null;
    const pipe = isCommand(s) ? s.stdin?.pipe : null;
    const mt = menu === s.id ? moveTargets(wf, s.id) : null;
    const title = s.label ?? s.id;
    const act = (m: Move | null) => () => { setMenu(null); move(s.id, m); };
    return (
      <li key={s.id} className="item">
        <div
          id={`blk-${s.id}`}
          role="group"
          aria-label={[title, t(`kind.${kind}`), safety ? t(`safety.${safety}`) : ""].filter(Boolean).join(", ")}
          aria-current={selected === s.id ? "true" : undefined}
          className={`blk kind-${kind}${safety ? ` safety-${safety}` : ""}${selected === s.id ? " sel" : ""}`}
          tabIndex={0}
          draggable
          onClick={(e) => { e.stopPropagation(); onSelect(s.id); }}
          onDragStart={(e) => { e.dataTransfer.setData("text/plain", s.id); e.dataTransfer.effectAllowed = "move"; setDrag(s.id); }}
          onDragEnd={() => { setDrag(null); setOver(null); }}
          onKeyDown={(e) => {
            if (e.target !== e.currentTarget) return; // keys inside the menu belong to the menu
            const m = moveTargets(wf, s.id);
            if (e.altKey && e.key === "ArrowUp") move(s.id, m.up);
            else if (e.altKey && e.key === "ArrowDown") move(s.id, m.down);
            else if (e.altKey && e.key === "ArrowRight") move(s.id, m.into[0] ?? null);
            else if (e.altKey && e.key === "ArrowLeft") move(s.id, m.out);
            else if (e.key === "Delete" || e.key === "Backspace") remove(s.id);
            else if (e.key === "Enter") onSelect(s.id);
            else return;
            e.preventDefault(); // Alt+Left would otherwise navigate back
          }}
        >
          <div className={`blk-head ${headClass(s, isToolStep(s) ? categoryOf(s.tool) : null)}`}>
            <span className="blk-title">{title}</span>
            <span className="badge">{t(`kind.${kind}`)}</span>
            {safety && <span className={`badge badge--${safety}`}>{t(`safety.${safety}`)}</span>}
            <button className="blk-menu-btn btn--icon" aria-label={t("blocks.menu", { id: s.id })} aria-expanded={menu === s.id}
              onClick={(e) => { e.stopPropagation(); setMenu(menu === s.id ? null : s.id); }}>⋯</button>
          </div>
          <div className="blk-sub">{subtitle(s)}</div>
          {pipe && <span className="badge badge--data blk-pipe">{t("blocks.pipe", { id: pipe })}</span>}
          {mt && (
            <div className="blk-menu" role="group" aria-label={t("blocks.menu", { id: s.id })}
              onClick={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); setMenu(null); } }}>
              <button disabled={!mt.up} onClick={act(mt.up)}>{t("blocks.up")}</button>
              <button disabled={!mt.down} onClick={act(mt.down)}>{t("blocks.down")}</button>
              {mt.into.map((i) => <button key={i.path.join("/")} onClick={act(i)}>{t("blocks.into", { target: i.label })}</button>)}
              <button disabled={!mt.out} onClick={act(mt.out)}>{t("blocks.out")}</button>
              <button className="btn--danger" onClick={() => { setMenu(null); remove(s.id); }}><Icon name="trash" />{t("blocks.delete")}</button>
            </div>
          )}
        </div>
        {b.slots.map((sl) => (
          <div key={sl.port} className="slot" role="group" aria-label={`${title}: ${t(`blocks.slot.${sl.port}`)}`}>
            <div className="slot-label">{t(`blocks.slot.${sl.port}`)}</div>
            {seq(sl.blocks, sl.path)}
          </div>
        ))}
      </li>
    );
  };

  return (
    <section className="panel canvas" aria-labelledby="canvas-h">
      <h2 id="canvas-h" className="sr-only">{t("canvas.title")}</h2>
      <div className="toolbar" role="toolbar" aria-label={t("canvas.toolbar")}>
        <label className="tb-field">{t("canvas.name")} <input value={wf.name} onChange={(e) => edit((w) => ({ ...w, name: e.target.value }), "name")} /></label>
        <span className="tb-spacer" />
        <HelpButton section="build" topic={t("canvas.title")} />
      </div>
      <div className="blocks" onClick={() => onSelect(null)} onKeyDown={(e) => { if (e.key === "Escape") { setAdding(null); setMenu(null); } }}>{seq(tree, [], true)}</div>
      <div aria-live="polite" className="sr-only">{live}</div>
    </section>
  );
}
