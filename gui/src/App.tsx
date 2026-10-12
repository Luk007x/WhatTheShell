// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { errMsg, getSettings, getStatus, getTool, hasToken, postSelftest, validateWorkflow } from "./api";
import { BlockView } from "./blocks/BlockView";
import { Canvas, type Edit } from "./canvas/Canvas";
import { AiContext } from "./ai/AiDialog";
import { FileMenu } from "./files/FileMenu";
import { RunPanel } from "./run/RunPanel";
import { CatalogPanel } from "./catalog/CatalogPanel";
import { clearToolCache, StepPanel } from "./detail/StepPanel";
import { ModulesView } from "./modules/ModulesView";
import { Templates } from "./catalog/Templates";
import { applyFontSize, loadAutoPreview, loadFontSize, saveAutoPreview, saveFontSize, Settings, type FontSize } from "./Settings";
import { mergeTemplate } from "./model/templates";
import { VariablesPanel } from "./detail/VariablesPanel";
import { useDebounced } from "./hooks";
import { Icon } from "./icons";
import { Resizer } from "./Resizer";
import { getLang, setLang, t, type Lang } from "./i18n";
import { captureOutput, evaluateOutput, findStep, newId, removeStep, renameStep, setVariables, stepIdAtErrorPath, updateStep, type OpResult } from "./model/ops";
import type { SandboxStatus, ToolInfo, ToolSummary } from "./types/api";
import type { Workflow } from "./types/workflow";

const msg = errMsg;
const MAX_HISTORY = 100;
type View = "graph" | "blocks";
const loadView = (): View => {
  try { return localStorage.getItem("wts.view") === "blocks" ? "blocks" : "graph"; } catch { return "graph"; }
};
const emptyWorkflow = (): Workflow => ({ schema_version: 1, name: "", steps: [] });

/** Modes of the mode bar; a new mode is one entry here plus one case in `center`. */
const MODES = ["build", "modules"] as const;
type Mode = (typeof MODES)[number];

/** Widths of the side columns in px (the middle takes the rest), kept in localStorage. */
type Cols = { catalog: number; details: number };
const COLS_KEY = "wts.cols";
const loadCols = (): Cols => {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(COLS_KEY) ?? "null");
    if (raw && typeof raw === "object" && "catalog" in raw && "details" in raw && typeof raw.catalog === "number" && typeof raw.details === "number") {
      return { catalog: raw.catalog, details: raw.details };
    }
  } catch { /* unreadable: defaults */ }
  return { catalog: 256, details: 360 };
};

interface State {
  doc: Workflow;
  past: Workflow[];
  future: Workflow[];
  warnings: string[];
  lastKey: string | null;
  /** Bumped by undo/redo/load so form drafts remount and show the document value. */
  epoch: number;
}
type Action =
  | { type: "edit"; op: (wf: Workflow) => OpResult | Workflow; key?: string }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "load"; doc: Workflow };

const asResult = (r: OpResult | Workflow): OpResult => ("wf" in r ? r : { wf: r, warnings: [] });

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case "edit": {
      const { wf, warnings } = asResult(a.op(s.doc));
      if (wf === s.doc) return { ...s, warnings };
      const coalesce = a.key !== undefined && a.key === s.lastKey; // typing in one field is one undo step
      const past = coalesce ? s.past : [...s.past, s.doc].slice(-MAX_HISTORY);
      return { doc: wf, past, future: [], warnings, lastKey: a.key ?? null, epoch: s.epoch };
    }
    case "undo": {
      const prev = s.past[s.past.length - 1];
      return prev ? { doc: prev, past: s.past.slice(0, -1), future: [s.doc, ...s.future], warnings: [], lastKey: null, epoch: s.epoch + 1 } : s;
    }
    case "redo": {
      const [next, ...rest] = s.future;
      return next ? { doc: next, past: [...s.past, s.doc], future: rest, warnings: [], lastKey: null, epoch: s.epoch + 1 } : s;
    }
    case "load":
      return { doc: a.doc, past: [], future: [], warnings: [], lastKey: null, epoch: s.epoch + 1 };
  }
}

function warningText(w: string): string {
  const [kind, a, b] = w.split(":");
  return t(`warn.${kind}`, { a: a ?? "", b: b ?? "" });
}

export function App() {
  const [, bump] = useState(0); // re-render on language change; t() reads module state
  const [sandbox, setSandbox] = useState<SandboxStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [catalogTool, setCatalogTool] = useState<string | null>(null);
  const [tool, setTool] = useState<ToolInfo | null>(null);
  const [toolError, setToolError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [safety, setSafety] = useState<Record<string, string>>({});
  const [category, setCategory] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<Mode>("build");
  const [notice, setNotice] = useState<string | null>(null);
  const [cols, setColsState] = useState<Cols>(loadCols);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [fontSize, setFontSize] = useState<FontSize>(loadFontSize);
  const [autoPreview, setAutoPreview] = useState(loadAutoPreview);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [refresh, setRefresh] = useState(0); // bumped when ToolInfos must be reloaded (language, module saved)
  const [view, setViewState] = useState<View>(loadView);
  const [outputOpen, setOutputOpen] = useState(true);
  const [fileId, setFileId] = useState<string | null>(null);
  const [savedJson, setSavedJson] = useState(JSON.stringify(emptyWorkflow()));
  const [validation, setValidation] = useState<{ ok: boolean; errors: { path: string; message: string }[] } | "checking" | string>("checking");
  const [state, dispatch] = useReducer(reducer, { doc: emptyWorkflow(), past: [], future: [], warnings: [], lastKey: null, epoch: 0 });
  const token = hasToken();
  const wf = state.doc;
  const dirty = useMemo(() => JSON.stringify(wf) !== savedJson, [wf, savedJson]);

  useEffect(() => { document.title = `${dirty ? "* " : ""}${wf.name || t("file.untitled")} – ${t("app.name")}`; }, [dirty, wf.name]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  useEffect(() => { applyFontSize(fontSize); }, [fontSize]);
  const edit: Edit = useCallback((op, key) => dispatch({ type: "edit", op, key }), []);
  const onLoaded = useCallback((tools: ToolSummary[]) => {
    setSafety((m) => ({ ...m, ...Object.fromEntries(tools.flatMap((x) => (x.safety ? [[x.name, x.safety]] : []))) }));
    setCategory((m) => ({ ...m, ...Object.fromEntries(tools.flatMap((x) => (x.category ? [[x.name, x.category]] : []))) }));
  }, []);
  const safetyOf = useCallback((name: string) => safety[name] ?? null, [safety]);
  const categoryOf = useCallback((name: string) => category[name] ?? null, [category]);
  const setCols = (next: Cols) => {
    setColsState(next);
    try { localStorage.setItem(COLS_KEY, JSON.stringify(next)); } catch { /* storage unavailable: widths last for this session */ }
  };

  useEffect(() => {
    if (!token) return;
    getSettings().then((x) => setAiEnabled(x.ai.enabled), () => undefined); // without settings the AI stays off
    getStatus().then((s) => setSandbox(s.sandbox)).catch((e: unknown) => setStatusError(msg(e)));
  }, [token]);

  useEffect(() => {
    if (!catalogTool) return;
    let stale = false;
    setTool(null);
    setToolError(null);
    getTool(catalogTool).then((x) => { if (!stale) setTool(x); }).catch((e: unknown) => { if (!stale) setToolError(msg(e)); });
    return () => { stale = true; };
  }, [catalogTool, refresh]);

  // validation, debounced; the backend is the authority
  const docKey = useDebounced(wf, 500);
  useEffect(() => {
    if (!token) return;
    let stale = false;
    validateWorkflow(docKey)
      .then((r) => { if (!stale) setValidation(r); })
      .catch((e: unknown) => { if (!stale) setValidation(msg(e)); });
    return () => { stale = true; };
  }, [docKey, token]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "z") return;
      // leave native text undo alone inside form fields and while a dialog is open
      if (e.target instanceof HTMLElement && e.target.closest("input, textarea, select, dialog")) return;
      if (document.querySelector("dialog[open]")) return;
      e.preventDefault();
      dispatch({ type: e.shiftKey ? "redo" : "undo" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const setView = (v: View) => {
    setViewState(v);
    try { localStorage.setItem("wts.view", v); } catch { /* storage unavailable: the choice lasts for this session */ }
  };
  const newDoc = () => { setSelected(null); setFileId(null); setSavedJson(JSON.stringify(emptyWorkflow())); dispatch({ type: "load", doc: emptyWorkflow() }); };
  const changeLang = (l: Lang) => { setLang(l); document.documentElement.lang = l; bump((n) => n + 1); setRefresh((n) => n + 1); };
  document.documentElement.lang = getLang();

  const hit = selected ? findStep(wf, selected) : undefined;
  const selStep = hit?.step;
  const retest = useCallback(() => { postSelftest().then(setSandbox, (e: unknown) => setStatusError(msg(e))); }, []);

  if (!token) return <main className="fatal" role="alert"><h1>{t("app.name")}</h1><p>{t("token.missing")}</p></main>;

  const sandboxText = sandbox ? (sandbox.available ? t("sandbox.ok") : t("sandbox.missing")) : t("sandbox.unknown");
  const sandboxClass = sandbox ? (sandbox.available ? "safe" : "dangerous") : "caution";
  const sandboxTip = sandbox && !sandbox.available ? `${sandboxText}: ${sandbox.reason} ${sandbox.install_hint}` : (statusError ?? sandboxText);
  const cmd = tool?.command;

  const center = (() => {
    switch (mode) {
      case "modules":
        return <ModulesView catalogTool={catalogTool} onChanged={() => { clearToolCache(); setRefresh((n) => n + 1); }} />;
      case "build":
        return view === "graph"
          ? <Canvas wf={wf} selected={selected} onSelect={setSelected} edit={edit} catalogTool={catalogTool} safetyOf={safetyOf} categoryOf={categoryOf} onNotice={setNotice} />
          : <BlockView wf={wf} selected={selected} onSelect={setSelected} edit={edit} catalogTool={catalogTool} safetyOf={safetyOf} categoryOf={categoryOf} />;
    }
  })();
  const maxCol = Math.max(320, Math.round(window.innerWidth * 0.4));

  return (
    <AiContext.Provider value={{ enabled: aiEnabled, openSettings: () => setSettingsOpen(true) }}>
    <div className={`app${outputOpen ? "" : " output-closed"}`}>
      <a className="skip" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>{t("a11y.skip")}</a>

      {/* Kopfzeile: name, file, history, status, settings */}
      <header className="app-header">
        <h1 className="brand">{t("app.name")}</h1>
        <FileMenu wf={wf} fileId={fileId} dirty={dirty}
          onLoad={(doc, id) => { dispatch({ type: "load", doc }); setSavedJson(JSON.stringify(doc)); setFileId(id); setSelected(null); }}
          onSaved={(id) => { setFileId(id); setSavedJson(JSON.stringify(wf)); }}
          onDeleted={(id) => { if (id === fileId) setFileId(null); }}
          onNew={newDoc}
          onDraft={(doc) => { dispatch({ type: "load", doc }); setSavedJson(JSON.stringify(emptyWorkflow())); setFileId(null); setSelected(null); }} />
        <span className="tb-group">
          <button disabled={state.past.length === 0} onClick={() => dispatch({ type: "undo" })}><Icon name="undo" />{t("history.undo")}</button>
          <button disabled={state.future.length === 0} onClick={() => dispatch({ type: "redo" })}><Icon name="redo" />{t("history.redo")}</button>
        </span>
        <span className="tb-spacer" />
        <span className="status-pill" title={sandboxTip} role="status" data-testid="sandbox-status" data-available={sandbox?.available ?? "unknown"}>
          <span className={`dot ${sandboxClass}`} aria-hidden="true" /> {sandboxText}
        </span>
        <button className="btn--icon" aria-label={t("settings.title")} title={t("settings.title")} onClick={() => setSettingsOpen(true)}><Icon name="settings" /></button>
      </header>

      {/* Modusleiste: one button per mode, view switch of the build mode */}
      <nav className="modebar">
        <div role="group" aria-label={t("mode.label")} className="segmented">
          {MODES.map((m) => <button key={m} aria-pressed={mode === m} onClick={() => setMode(m)}>{t(`mode.${m}`)}</button>)}
        </div>
        {mode === "build" && (
          <div role="group" aria-label={t("view.label")} className="segmented">
            {(["graph", "blocks"] as const).map((v) => (
              <button key={v} aria-pressed={view === v} onClick={() => setView(v)}><Icon name={v} />{t(`view.${v}`)}</button>
            ))}
          </div>
        )}
      </nav>

      {/* Hauptgrid: catalog | center | details */}
      <main id="main" tabIndex={-1} className="app-main"
        style={{ gridTemplateColumns: `minmax(12rem, ${cols.catalog}px) auto minmax(18rem, 1fr) auto minmax(16rem, ${cols.details}px)` }}>
        <CatalogPanel selected={catalogTool} onSelect={setCatalogTool} onLoaded={onLoaded} reloadKey={refresh} />
        <Resizer label={t("layout.catalog")} value={cols.catalog} min={192} max={maxCol} onChange={(catalog) => setCols({ ...cols, catalog })} />
        {center}
        <Resizer label={t("layout.details")} value={cols.details} min={256} max={maxCol} invert onChange={(details) => setCols({ ...cols, details })} />
        <section className="panel" aria-labelledby="details-h">
          <div className="panel__header"><h2 id="details-h">{t("details.title")}</h2></div>
          <div className="panel__body">
          {selStep ? (
            <StepPanel key={`${selStep.id}:${state.epoch}:${refresh}`} autoPreview={autoPreview} step={selStep} wf={wf} sandbox={sandbox} onRetest={retest}
              update={(patch, key) => edit((w) => updateStep(w, selStep.id, patch), key ? `${selStep.id}:${key}` : undefined)}
              rename={(n) => {
                const r = renameStep(wf, selStep.id, n);
                edit((w) => renameStep(w, selStep.id, n));
                if (r.wf !== wf) setSelected(n); // refused renames keep the selection
              }}
              remove={() => { edit((w) => removeStep(w, selStep.id)); setSelected(null); }} />
          ) : (
            <VariablesPanel key={state.epoch} variables={wf.variables} onChange={(v) => edit((w) => setVariables(w, v), "vars")} />
          )}
          {!selStep && catalogTool && (
            <section aria-label={t("details.title")} className="tool-info">
              {toolError && <p role="alert" className="error">{t("error.network", { message: toolError })}</p>}
              {cmd && (
                <div>
                  <h3>{cmd.display_name ?? tool.name}</h3>
                  {cmd.summary && <p>{cmd.summary}</p>}
                  {cmd.usage && <><h4>{t("details.usage")}</h4><pre className="code">{cmd.usage}</pre></>}
                </div>
              )}
              <Templates tool={catalogTool} onInsert={(doc) => { edit((w) => mergeTemplate(w, doc)); setSelected(null); }} />
            </section>
          )}
          </div>
        </section>
      </main>

      {/* Fuss: status line, validation errors, run panel */}
      <footer className="app-footer">
        <div className="statusbar">
          <p className="statusline" role="status">
            <span className={`dot ${validation === "checking" ? "caution" : typeof validation === "string" || !validation.ok ? "dangerous" : "safe"}`} aria-hidden="true" />
            {validation === "checking" ? t("status.checking") : typeof validation === "string" ? `${t("error.prefix")}: ${validation}`
              : validation.ok ? t("status.valid") : t("status.invalid", { n: validation.errors.length })}
            {state.warnings.map((w) => <span key={w} className="hint"> · {warningText(w)}</span>)}
            {notice && <span className="notice"> · {notice}</span>}
          </p>
          <button aria-expanded={outputOpen} onClick={() => setOutputOpen(!outputOpen)}>
            {t(outputOpen ? "output.hide" : "output.show")}
          </button>
        </div>
        {typeof validation === "object" && !validation.ok && (
          <ul className="errors">
            {validation.errors.map((e, i) => {
              const id = stepIdAtErrorPath(wf, e.path);
              return (
                <li key={i}>
                  {id ? <button className="btn--sm" onClick={() => setSelected(id)}>{id}</button> : null} <code>{e.path}</code> {e.message}
                </li>
              );
            })}
          </ul>
        )}
        <div className="footer-body" hidden={!outputOpen}>
          <RunPanel wf={wf} onSelectStep={setSelected}
            onCapture={(id) => edit((w) => captureOutput(w, id))}
            onEvaluate={(id) => { const created = newId(wf, `${id}_pruefe`); edit((w) => evaluateOutput(w, id)); setSelected(created); }} />
        </div>
      </footer>
      <Settings open={settingsOpen} onClose={() => setSettingsOpen(false)} onAiChanged={setAiEnabled} lang={getLang()} onLang={changeLang}
        fontSize={fontSize} onFontSize={(s) => { saveFontSize(s); setFontSize(s); }}
        autoPreview={autoPreview} onAutoPreview={(on) => { saveAutoPreview(on); setAutoPreview(on); }} />
    </div>
    </AiContext.Provider>
  );
}
