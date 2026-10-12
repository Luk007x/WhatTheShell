// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, errMsg, getModule, listModules, listTools, scaffoldModule, type ModuleList } from "../api";
import { t } from "../i18n";
import { Icon } from "../icons";
import { ErrorBoundary } from "./ErrorBoundary";
import { ModuleEditor, type EditorInit } from "./ModuleEditor";
import { parseRaw } from "./moduleForm";

export function ModulesView({ catalogTool, onChanged }: { catalogTool: string | null; onChanged: (tool: string) => void }) {
  const [list, setList] = useState<ModuleList | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [init, setInit] = useState<(EditorInit & { key: number }) | null>(null);
  const [newTool, setNewTool] = useState(catalogTool ?? "");
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const dirty = useRef(false);
  const proceed = () => !dirty.current || window.confirm(t("mod.discard"));

  const reload = useCallback(() => { listModules().then(setList, (e: unknown) => setError(errMsg(e))); }, []);
  useEffect(() => {
    reload();
    listTools().then((ts) => setCategories([...new Set(ts.flatMap((x) => (x.category ? [x.category] : [])))].sort()), () => undefined); // categories are only a suggestion list
  }, [reload]);

  const open = (next: EditorInit) => { setError(null); setMissing(null); setInit({ ...next, key: Date.now() }); };
  const select = (tool: string) => {
    if (!proceed()) return;
    getModule(tool).then((m) => open({ tool, raw: m.raw, source: m.source }), (e: unknown) => {
      if (e instanceof ApiError && e.status === 404) { setNewTool(tool); setMissing(tool); setInit(null); } else setError(errMsg(e));
    });
  };
  const scaffold = () => {
    const tool = newTool.trim();
    if (tool && proceed()) scaffoldModule(tool).then((r) => open({ tool, raw: r.raw, source: null }), (e: unknown) => setError(errMsg(e)));
  };
  const importFile = (file: File | undefined) => {
    if (!file || !proceed()) return;
    file.text().then((raw) => {
      const p = parseRaw(raw);
      const tool = p.ok && typeof p.doc.tool === "string" ? p.doc.tool : file.name.replace(/\.module\.ya?ml$/, "");
      open({ tool, raw, source: null });
    }, (e: unknown) => setError(errMsg(e)));
  };
  const place = (path: string) => {
    const i = (list?.search_paths ?? []).findIndex((s) => path.startsWith(`${s.dir}/`) && !path.slice(s.dir.length + 1).includes("/"));
    return i === 0 ? t("mod.source.bundled") : i === 1 ? t("mod.source.user") : t("mod.source.project");
  };

  return (
    <section className="panel canvas modules" aria-labelledby="canvas-h">
      <div className="panel__header"><h2 id="canvas-h">{t("mod.title")}</h2></div>
      {error && <p role="alert" className="error">{error}</p>}
      <div className="toolbar">
        <label className="tb-field">{t("mod.newtool")} <input value={newTool} onChange={(e) => setNewTool(e.target.value)} /></label>
        <button onClick={scaffold}><Icon name="plus" />{t("mod.scaffold")}</button>
        <label className="filebtn">{t("mod.import")} <input type="file" accept=".yaml,.yml" onChange={(e) => { importFile(e.target.files?.[0]); e.target.value = ""; }} /></label>
      </div>
      {missing && <p role="status" className="hint">{t("mod.missing", { tool: missing })}</p>}
      <div className="modules-body">
        <div className="modules-list">
          <h3>{t("mod.paths")}</h3>
          <ul>{list?.search_paths.map((s) => <li key={s.dir}><code>{s.dir}</code> ({s.exists ? t("mod.count", { n: s.count }) : t("mod.nodir")})</li>)}</ul>
          <h3>{t("mod.list")}</h3>
          <ul className="tools">
            {list?.modules.map((m) => (
              <li key={m.path}><button className="tool" onClick={() => select(m.tool)}><span className="name">{m.tool}</span><span className="summary">{place(m.path)}</span></button></li>
            ))}
          </ul>
          {list && list.errors.length > 0 && (
            <>
              <h3>{t("mod.errors")}</h3>
              <ul className="errors" role="alert">{list.errors.map((e, i) => <li key={i}><code>{e.path}{e.line ? `:${e.line}` : ""}</code>: {e.message}</li>)}</ul>
            </>
          )}
        </div>
        {init && (
          <ErrorBoundary key={init.key} onReset={() => setInit(null)}>
            <ModuleEditor init={init} categories={categories} dirtyRef={dirty}
              onSaved={(tool) => { reload(); onChanged(tool); }}
              onDeleted={(tool) => { setInit(null); reload(); onChanged(tool); }} />
          </ErrorBoundary>
        )}
      </div>
    </section>
  );
}
