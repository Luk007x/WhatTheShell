// SPDX-License-Identifier: AGPL-3.0-or-later
// Module editor: raw YAML is the source of truth, the form patches the parsed document (F-25).
import { useEffect, useState, type KeyboardEvent, type MutableRefObject } from "react";
import { ApiError, deleteModule, errMsg, putModule } from "../api";
import { t } from "../i18n";
import { flagsToText, parseRaw, setField, setRowField, str, textToFlags, toRaw, exampleTitles, validRows, type Doc, type RowList } from "./moduleForm";

export interface EditorInit { tool: string; raw: string; source: "user" | "bundled" | null }
type Problem = { path: string; line?: number | null; message: string };

const TYPES = ["string", "int", "float", "bool", "path", "enum", "secret"];
const IMPORTANCE = ["common", "normal", "rare"];
const SAFETY = ["safe", "caution", "dangerous"];

function Select({ value, values, label, onChange }: { value: string; values: string[]; label: string; onChange: (v: string) => void }) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="" />
      {value && !values.includes(value) && <option value={value}>{value}</option>}
      {values.map((v) => <option key={v} value={v}>{v}</option>)}
    </select>
  );
}

function Rows({ doc, list, cols, onDoc }: {
  doc: Doc; list: RowList; onDoc: (d: Doc) => void;
  cols: { key: string; kind: "text" | "flags" | "type" | "importance" | "safety" | "bool" }[];
}) {
  const { rows, bad } = validRows(doc, list);
  if (rows.length === 0 && bad === 0) return null;
  return (
    <>
    {bad > 0 && <p role="alert" className="error">{t("mod.badrows", { n: bad })}</p>}
    {rows.length > 0 && <table>
      <caption className="sr-only">{t(`mod.${list}`)}</caption>
      <thead><tr>{cols.map((c) => <th key={c.key} scope="col">{t(`mod.col.${c.key}`)}</th>)}</tr></thead>
      <tbody>
        {rows.map(({ row: r, index: i }) => (
          <tr key={`${i}:${str(r.id)}`}>
            {cols.map((c) => {
              const label = `${str(r.id)}: ${t(`mod.col.${c.key}`)}`;
              const set = (v: unknown) => onDoc(setRowField(doc, list, i, c.key, v));
              const v = r[c.key];
              return (
                <td key={c.key}>
                  {c.key === "id" ? <code>{str(v)}</code>
                    : c.kind === "flags" ? <input aria-label={label} value={flagsToText(v)} onChange={(e) => set(textToFlags(e.target.value))} />
                    : c.kind === "type" ? <Select label={label} value={str(v)} values={TYPES} onChange={set} />
                    : c.kind === "importance" ? <Select label={label} value={str(v)} values={IMPORTANCE} onChange={set} />
                    : c.kind === "safety" ? <Select label={label} value={str(v)} values={SAFETY} onChange={set} />
                    : c.kind === "bool" ? <input type="checkbox" aria-label={label} checked={v === true} onChange={(e) => set(e.target.checked || undefined)} />
                    : <input aria-label={label} value={str(v)} onChange={(e) => set(e.target.value)} />}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>}
    </>
  );
}

export function ModuleEditor({ init, categories, onSaved, onDeleted, dirtyRef }: {
  init: EditorInit; categories: string[]; onSaved: (tool: string) => void; onDeleted: (tool: string) => void;
  /** Set to true while the raw text differs from the last loaded/saved text. */
  dirtyRef: MutableRefObject<boolean>;
}) {
  const [raw, setRaw] = useState(init.raw);
  const [source, setSource] = useState(init.source);
  const [base, setBase] = useState(init.tool); // the module this editor was opened for; delete targets this one
  const [clean, setClean] = useState(init.raw);
  useEffect(() => { dirtyRef.current = raw !== clean; }, [raw, clean, dirtyRef]);
  useEffect(() => () => { dirtyRef.current = false; }, [dirtyRef]);
  const [tab, setTab] = useState<"form" | "raw">("raw");
  const [tabError, setTabError] = useState<string | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [saved, setSaved] = useState(false);
  const parsed = parseRaw(raw);

  const edit = (v: string) => { setRaw(v); setSaved(false); };
  const show = (next: "form" | "raw") => {
    if (next === "form" && !parsed.ok) { setTabError(t("mod.syntax", { message: parsed.error })); return; }
    setTabError(null);
    setTab(next);
  };
  const tool = parsed.ok && typeof parsed.doc.tool === "string" ? parsed.doc.tool : base;

  const save = () => {
    setProblems([]);
    if (tool !== base && !window.confirm(t("mod.rename.confirm", { tool }))) return;
    putModule(tool, raw).then(() => { setSaved(true); setSource("user"); setBase(tool); setClean(raw); onSaved(tool); }, (e: unknown) => {
      setSaved(false);
      setProblems(e instanceof ApiError && e.errors.length > 0 ? e.errors : [{ path: "", message: errMsg(e) }]);
    });
  };
  const remove = () => {
    if (!window.confirm(t("mod.delete.confirm", { tool: base }))) return;
    deleteModule(base).then(() => onDeleted(base), (e: unknown) => setProblems([{ path: "", message: errMsg(e) }]));
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([raw], { type: "text/yaml" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${tool}.module.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const onTab = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== "Tab" || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey) return;
    e.preventDefault();
    e.currentTarget.setRangeText("  ", e.currentTarget.selectionStart, e.currentTarget.selectionEnd, "end");
    edit(e.currentTarget.value);
  };

  const doc = parsed.ok ? parsed.doc : {};
  const patch = (key: string) => (v: string) => edit(toRaw(setField(doc, key, v)));
  const field = (key: string, rows = 0) => (
    <div className="field">
      <label htmlFor={`mf-${key}`}>{t(`mod.col.${key}`)}</label>
      {rows ? <textarea id={`mf-${key}`} rows={rows} value={str(doc[key])} onChange={(e) => patch(key)(e.target.value)} />
        : <input id={`mf-${key}`} value={str(doc[key])} list={key === "category" ? "mf-categories" : undefined} onChange={(e) => patch(key)(e.target.value)} />}
    </div>
  );

  return (
    <div className="mod-editor">
      <h3>{tool} <span className="muted">{source ? t(`mod.source.${source}`) : t("mod.unsaved")}</span></h3>
      <div className="toolbar" role="toolbar" aria-label={t("canvas.toolbar")}>
        <div role="tablist" aria-label={t("mod.title")}>
          {(["form", "raw"] as const).map((k) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => show(k)}>{t(`mod.tab.${k}`)}</button>
          ))}
        </div>
        <button onClick={save}>{t("file.save")}</button>
        <button onClick={download}>{t("mod.export")}</button>
        <button disabled={source !== "user"} onClick={remove}>{t("file.delete")}</button>
      </div>
      {tabError && <p role="alert" className="error">{tabError}</p>}
      {saved && <p role="status" className="hint">{t("mod.saved")}</p>}
      {problems.length > 0 && (
        <ul role="alert" className="errors" data-testid="mod-errors">
          {problems.map((p, i) => <li key={i}><code>{p.path}{p.line ? `:${p.line}` : ""}</code> {p.message}</li>)}
        </ul>
      )}
      {tab === "raw" ? (
        <textarea className="rawyaml" aria-label={t("mod.tab.raw")} spellCheck={false} rows={28} value={raw}
          onChange={(e) => edit(e.target.value)} onKeyDown={onTab} />
      ) : (
        <div role="tabpanel">
          <p className="muted">{t("mod.comments")}</p>
          <datalist id="mf-categories">{categories.map((c) => <option key={c} value={c} />)}</datalist>
          {field("display_name")}
          {field("category")}
          {field("summary")}
          {field("description", 4)}
          <div className="field">
            <label htmlFor="mf-safety">{t("mod.col.safety")}</label>
            <select id="mf-safety" value={str(doc.safety)} onChange={(e) => patch("safety")(e.target.value)}>
              <option value="" />
              {SAFETY.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <h4>{t("mod.options")}</h4>
          <Rows doc={doc} list="options" onDoc={(d) => edit(toRaw(d))}
            cols={[{ key: "id", kind: "text" }, { key: "flags", kind: "flags" }, { key: "label", kind: "text" }, { key: "help", kind: "text" }, { key: "group", kind: "text" },
              { key: "importance", kind: "importance" }, { key: "safety", kind: "safety" }, { key: "type", kind: "type" }]} />
          <h4>{t("mod.inputs")}</h4>
          <Rows doc={doc} list="inputs" onDoc={(d) => edit(toRaw(d))}
            cols={[{ key: "id", kind: "text" }, { key: "label", kind: "text" }, { key: "help", kind: "text" }, { key: "type", kind: "type" }, { key: "required", kind: "bool" }]} />
          <h4>{t("mod.examples")}</h4>
          <ul>{exampleTitles(doc).map((x, i) => <li key={i}>{x}</li>)}</ul>
          <p className="muted">{t("mod.examples.hint")}</p>
        </div>
      )}
    </div>
  );
}
