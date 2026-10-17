// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { errMsg, getSettings, getStatus, getTool, hasToken, postSelftest, validateWorkflow } from "./api";
import { BlockView } from "./blocks/BlockView";
import { Canvas, type Edit } from "./canvas/Canvas";
import { Help, HelpContext, type HelpSection } from "./Help";
import { commandStep } from "./model/blocks";
import { AiContext } from "./ai/AiDialog";
import { FileMenu } from "./files/FileMenu";
import { RunPanel } from "./run/RunPanel";
import { RunView } from "./run/RunView";
import { CatalogPanel } from "./catalog/CatalogPanel";
import { clearToolCache, StepPanel } from "./detail/StepPanel";
import { ModulesView } from "./modules/ModulesView";
import { Templates } from "./catalog/Templates";
import { applyFontSize, initialModeView, loadAutoPreview, loadFontSize, loadHelpStart, loadStartView, saveAutoPreview, saveFontSize, Settings, shouldOpenHelp, type FontSize } from "./Settings";
import { mergeTemplate } from "./model/templates";
import { VariablesPanel } from "./detail/VariablesPanel";
import { useDebounced } from "./hooks";
import { Icon } from "./icons";
import { ManualView } from "./manual/ManualView";
import { applyTheme, getTheme, setTheme, THEMES, type Theme } from "./theme";
import { Modal } from "./Modal";
import { clampCol, COL_MIN, colMax, Resizer } from "./Resizer";
import { getLang, setLang, t, type Lang } from "./i18n";
import { addStep, captureOutput, evaluateOutput, findStep, newId, removeStep, renameStep, setVariables, stepIdAtErrorPath, updateStep, type OpResult } from "./model/ops";
import type { SandboxStatus, ToolInfo, ToolSummary, ValidationResult } from "./types/api";
import type { Workflow } from "./types/workflow";

const msg = errMsg;
const MAX_HISTORY = 100;
type View = "graph" | "blocks";
const loadView = (): View => {
  try { return localStorage.getItem("wts.view") === "blocks" ? "blocks" : "graph"; } catch { return "graph"; }
};
const helpSeen = (): boolean => {
  try { return localStorage.getItem("wts.helpseen") !== null; } catch { return true; } // no storage: never nag
};
const THEME_ICON = { system: "contrast", light: "sun", dark: "moon" } as const satisfies Record<Theme, string>;
const emptyWorkflow = (): Workflow => ({ schema_version: 1, name: "", steps: [] });

/** Modes of the mode bar; a new mode is one entry here plus one case in `center`. */
const MODES = ["build", "run", "modules"] as const;
type Mode = (typeof MODES)[number];
/** Accessible names that differ from the visible label: "Ausführen" alone would clash with the editor's run button. */
const MODE_ARIA: Partial<Record<Mode, string>> = { run: "mode.run.aria" };
const isMode = (x: unknown): x is Mode => MODES.some((m) => m === x);
const loadMode = (): Mode => {
  try { const m = localStorage.getItem("wts.mode"); return isMode(m) ? m : "build"; } catch { return "build"; }
};

/** Widths of the side columns in px (the middle takes the rest), kept in localStorage. */
type Cols = { catalog: number; details: number };
const COLS_KEY = "wts.cols";
const loadCols = (): Cols => {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(COLS_KEY) ?? "null");
    if (raw && typeof raw === "object" && "catalog" in raw && "details" in raw && typeof raw.catalog === "number" && typeof raw.details === "number"
      && Number.isFinite(raw.catalog) && Number.isFinite(raw.details)) {
      const max = colMax();
      return { catalog: clampCol(raw.catalog, COL_MIN.catalog, max), details: clampCol(raw.details, COL_MIN.details, max) };
    }
  } catch { /* unreadable: defaults */ }
  return { catalog: 256, details: 420 };
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
  const [start] = useState(() => initialModeView(loadStartView(), loadMode(), loadView(), { build: "build", run: "run", modules: "modules" }, { graph: "graph", blocks: "blocks" }));
  const [mode, setModeState] = useState<Mode>(start.mode);
  const [notice, setNotice] = useState<string | null>(null);
  const [cols, setColsState] = useState<Cols>(loadCols);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [fontSize, setFontSize] = useState<FontSize>(loadFontSize);
  const [autoPreview, setAutoPreview] = useState(loadAutoPreview);
  const [stopped, setStopped] = useState(false); // server quit: the app is replaced by the closing view, nothing is polled
  const [aiEnabled, setAiEnabled] = useState(false);
  const [refresh, setRefresh] = useState(0); // bumped when ToolInfos must be reloaded (language, module saved)
  const [view, setViewState] = useState<View>(start.view);
  const [theme, setThemeState] = useState<Theme>(getTheme);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [outputOpen, setOutputOpen] = useState(true);
  const [helpSection, setHelpSection] = useState<HelpSection | null>(null);
  const [manual, setManual] = useState<string | null>(null); // open manual: chapter id wanted first (null = closed)
  const [knownTools, setKnownTools] = useState<ReadonlySet<string>>(new Set());
  const [interactiveTools, setInteractiveTools] = useState<ReadonlySet<string>>(new Set());
  const saveRef = useRef<(() => void) | null>(null);
  const addToolRef = useRef<((tool: string) => void) | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);
  const [savedJson, setSavedJson] = useState(JSON.stringify(emptyWorkflow()));
  const [validation, setValidation] = useState<ValidationResult | "checking" | string>("checking");
  const [state, dispatch] = useReducer(reducer, { doc: emptyWorkflow(), past: [], future: [], warnings: [], lastKey: null, epoch: 0 });
  const token = hasToken();
  useEffect(() => { if (token && shouldOpenHelp(helpSeen(), loadHelpStart())) setHelpSection("start"); }, [token]); // first start
  const closeHelp = () => {
    setHelpSection(null);
    try { localStorage.setItem("wts.helpseen", "1"); } catch { /* storage unavailable: the help opens again next time */ }
  };
  const wf = state.doc;
  const editorBar = mode !== "run" && manual === null; // file menu and history belong to the editor
  const dirty = useMemo(() => JSON.stringify(wf) !== savedJson, [wf, savedJson]);

  useEffect(() => { document.title = (dirty ? "* " : "") + t("app.name"); }, [dirty]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  useEffect(() => { applyFontSize(fontSize); }, [fontSize]);
  const nextTheme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length] ?? "system";
  const themeLabel = t("theme.label", { cur: t(`theme.${theme}`), next: t(`theme.${nextTheme}`) });
  const cycleTheme = () => { setThemeState(nextTheme); setTheme(nextTheme); applyTheme(nextTheme); };
  const edit: Edit = useCallback((op, key) => dispatch({ type: "edit", op, key }), []);
  const onLoaded = useCallback((tools: ToolSummary[]) => {
    setKnownTools((s) => new Set([...s, ...tools.map((x) => x.name)]));
    setInteractiveTools((s) => new Set([...[...s].filter((n) => !tools.some((x) => x.name === n)), ...tools.filter((x) => x.interactive).map((x) => x.name)]));
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

  const missingTools = useMemo(
    () => new Map(typeof validation === "object" ? (validation.missing_tools ?? []).map((m) => [m.step, m.install] as const) : []),
    [validation]);
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
      const mod = e.ctrlKey || e.metaKey;
      const k = e.key.toLowerCase();
      // always swallowed: the browser's "save page" dialog is never wanted; the action itself needs the editor
      if (mod && k === "s") { e.preventDefault(); if (mode === "build" && !document.querySelector("dialog[open]")) saveRef.current?.(); return; }
      // leave native text editing alone inside form fields and while a dialog is open
      if (e.target instanceof HTMLElement && e.target.closest("input, textarea, select, dialog, [contenteditable]")) return;
      if (document.querySelector("dialog[open]")) return;
      if (e.key === "?") { e.preventDefault(); setHelpSection("keys"); return; }
      if (mode !== "build") return; // no editor shortcuts in the other modes
      if (mod && (k === "z" || k === "y")) { e.preventDefault(); dispatch({ type: k === "y" || e.shiftKey ? "redo" : "undo" }); }
      else if (e.key === "Escape") { setSelected(null); setNotice(null); } // Delete is handled by the canvas and the block view
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode]);

  const setView = (v: View) => {
    setViewState(v);
    try { localStorage.setItem("wts.view", v); } catch { /* storage unavailable: the choice lasts for this session */ }
  };
  const setMode = (m: Mode) => {
    setModeState(m);
    try { localStorage.setItem("wts.mode", m); } catch { /* storage unavailable: the mode lasts for this session */ }
  };
  const loadDoc = (doc: Workflow, id: string) => {
    dispatch({ type: "load", doc }); setSavedJson(JSON.stringify(doc)); setFileId(id); setSelected(null);
    if (mode === "run") setMode("build");
  };
  const newDoc = () => { setSelected(null); setFileId(null); setSavedJson(JSON.stringify(emptyWorkflow())); dispatch({ type: "load", doc: emptyWorkflow() }); };
  const changeLang = (l: Lang) => { setLang(l); document.documentElement.lang = l; bump((n) => n + 1); setRefresh((n) => n + 1); };
  document.documentElement.lang = getLang();

  const hit = selected ? findStep(wf, selected) : undefined;
  const selStep = hit?.step;
  const retest = useCallback(() => { postSelftest().then(setSandbox, (e: unknown) => setStatusError(msg(e))); }, []);

  if (stopped) return <main className="fatal" role="status"><h1>{t("app.name")}</h1><p>{t("quit.done")}</p></main>;
  if (!token) return <main className="fatal" role="alert"><h1>{t("app.name")}</h1><p>{t("token.missing")}</p></main>;

  const sandboxText = sandbox ? (sandbox.available ? t("sandbox.ok") : t("sandbox.missing")) : t("sandbox.unknown");
  const sandboxClass = sandbox ? (sandbox.available ? "safe" : "dangerous") : "caution";
  const sandboxTip = sandbox && !sandbox.available ? `${sandboxText}: ${sandbox.reason} ${sandbox.install_hint}` : (statusError ?? sandboxText);
  const cmd = tool?.command;

  const center = (() => {
    switch (mode) {
      case "modules":
        return <ModulesView catalogTool={catalogTool} onChanged={() => { clearToolCache(); setRefresh((n) => n + 1); }} />;
      case "run":
        return null; // RunView replaces the whole editor grid
      case "build":
        return view === "graph"
          ? <Canvas wf={wf} selected={selected} onSelect={setSelected} edit={edit} catalogTool={catalogTool} safetyOf={safetyOf} categoryOf={categoryOf} onNotice={setNotice} theme={theme} addToolRef={addToolRef} knownTools={knownTools} interactiveTools={interactiveTools} missingTools={missingTools} />
          : <BlockView wf={wf} selected={selected} onSelect={setSelected} edit={edit} catalogTool={catalogTool} safetyOf={safetyOf} categoryOf={categoryOf} knownTools={knownTools} interactiveTools={interactiveTools} missingTools={missingTools} />;
    }
  })();
  const detailsContent = (
    <>
          {selStep ? (
            <StepPanel missing={missingTools.has(selStep.id) ? { install: missingTools.get(selStep.id) ?? null } : undefined} key={`${selStep.id}:${state.epoch}:${refresh}`} autoPreview={autoPreview} step={selStep} wf={wf} sandbox={sandbox} onRetest={retest}
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
    </>
  );
  const maxCol = colMax();

  return (
    <AiContext.Provider value={{ enabled: aiEnabled, openSettings: () => setSettingsOpen(true) }}>
    <HelpContext.Provider value={setHelpSection}>
    <div className={`app${outputOpen ? "" : " output-closed"}`}>
      <a className="skip" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>{t("a11y.skip")}</a>

      {/* Kopfzeile: name, file, history, status, settings */}
      <header className="app-header">
        <h1 className="brand">{t("app.name")}</h1>
        {manual !== null && <button onClick={() => setManual(null)}>← {t("manual.back")}</button>}
        {editorBar && <FileMenu wf={wf} fileId={fileId} dirty={dirty}
          onLoad={loadDoc}
          onSaved={(id) => { setFileId(id); setSavedJson(JSON.stringify(wf)); setNotice(t("file.saved.run", { id })); }}
          onDeleted={(id) => { if (id === fileId) setFileId(null); }}
          onNew={newDoc} saveRef={saveRef}
          onDraft={(doc) => { dispatch({ type: "load", doc }); setSavedJson(JSON.stringify(emptyWorkflow())); setFileId(null); setSelected(null); }} />}
        {editorBar && <span className="tb-group">
          <button disabled={state.past.length === 0} onClick={() => dispatch({ type: "undo" })}><Icon name="undo" />{t("history.undo")}</button>
          <button disabled={state.future.length === 0} onClick={() => dispatch({ type: "redo" })}><Icon name="redo" />{t("history.redo")}</button>
        </span>}
        <span className="tb-spacer" />
        <span className="status-pill" title={sandboxTip} role="status" data-testid="sandbox-status" data-available={sandbox?.available ?? "unknown"}>
          <span className={`dot ${sandboxClass}`} aria-hidden="true" /> {sandboxText}
        </span>
        <button className="btn--icon" aria-label={t("manual.title")} title={t("manual.title")} onClick={() => setManual("")}><Icon name="book" /></button>
        <button className="btn--icon" aria-label={t("help.title")} title={t("help.title")} onClick={() => setHelpSection("start")}><Icon name="help" /></button>
        <button className="btn--icon" data-testid="theme-toggle" data-theme={theme} aria-label={themeLabel} title={themeLabel} onClick={cycleTheme}><Icon name={THEME_ICON[theme]} /></button>
        <button className="btn--icon" aria-label={t("settings.title")} title={t("settings.title")} onClick={() => setSettingsOpen(true)}><Icon name="settings" /></button>
      </header>

      {/* Modusleiste: one button per mode, view switch of the build mode */}
      <nav className="modebar" hidden={manual !== null}>
        <div role="group" aria-label={t("mode.label")} className="segmented">
          {MODES.map((m) => (
            <button key={m} aria-pressed={mode === m} aria-label={MODE_ARIA[m] && t(MODE_ARIA[m])} onClick={() => setMode(m)}>{t(`mode.${m}`)}</button>
          ))}
        </div>
        {mode === "build" && (
          <div role="group" aria-label={t("view.label")} className="segmented">
            {(["graph", "blocks"] as const).map((v) => (
              <button key={v} aria-pressed={view === v} onClick={() => setView(v)}><Icon name={v} />{t(`view.${v}`)}</button>
            ))}
          </div>
        )}
      </nav>

      {/* Ausführen: library | form, output below; replaces the editor grid and footer, stays mounted (hidden) in other modes */}
      <RunView active={mode === "run" && manual === null} onOpenInEditor={(doc, id) => { if (!dirty || window.confirm(t("file.discard"))) loadDoc(doc, id); }} />

      {/* Hauptgrid: catalog | center | details */}
      {manual !== null && <ManualView initial={manual} />}
      {mode !== "run" && manual === null && <main id="main" tabIndex={-1} className="app-main"
        style={{ gridTemplateColumns: `minmax(12rem, ${cols.catalog}px) auto minmax(18rem, 1fr) auto minmax(16rem, ${cols.details}px)` }}>
        <CatalogPanel selected={catalogTool} onSelect={setCatalogTool} onLoaded={onLoaded} reloadKey={refresh} onAdd={(name) => {
          if (mode !== "build") return;
          if (addToolRef.current) addToolRef.current(name); // graph view: honours the chosen target
          else { const step = commandStep(wf, name, { terminal: interactiveTools.has(name) }); edit((w) => addStep(w, step, [])); setSelected(step.id); }
        }} />
        <Resizer label={t("layout.catalog")} value={cols.catalog} min={COL_MIN.catalog} max={maxCol} onChange={(catalog) => setCols({ ...cols, catalog })} />
        {center}
        <Resizer label={t("layout.details")} value={cols.details} min={COL_MIN.details} max={maxCol} invert onChange={(details) => setCols({ ...cols, details })} />
        <section className="panel" aria-labelledby="details-h">
          <div className="panel__header">
            <h2 id="details-h">{t("details.title")}</h2>
            <button className="btn--icon" aria-label={t("details.expand")} title={t("details.expand")} onClick={() => setDetailsOpen(true)}><Icon name="expand" /></button>
          </div>
          <div className="panel__body">
          {detailsOpen ? (
            <>
              <p className="muted">{t("details.inwindow")}</p>
              <button onClick={() => setDetailsOpen(false)}>{t("details.collapse")}</button>
            </>
          ) : detailsContent}
          </div>
        </section>
      </main>}

      {/* Fuss: status line, validation errors, run panel */}
      {/* kept mounted in the run mode so a running editor run survives the switch */}
      <footer className="app-footer" hidden={mode === "run" || manual !== null}>
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
      <Modal open={detailsOpen} className="modal--wide" title={t("details.title")} onCancel={() => setDetailsOpen(false)}>
        {detailsContent}
        <div className="actions"><button data-autofocus onClick={() => setDetailsOpen(false)}>{t("details.collapse")}</button></div>
      </Modal>
      <Help section={helpSection} onSection={setHelpSection} onClose={closeHelp} onManual={(s) => { closeHelp(); setManual(s); }} />
      <Settings open={settingsOpen} onClose={() => setSettingsOpen(false)} onStopped={() => { setSettingsOpen(false); setStopped(true); }} onAiChanged={setAiEnabled} lang={getLang()} onLang={changeLang}
        fontSize={fontSize} onFontSize={(s) => { saveFontSize(s); setFontSize(s); }}
        autoPreview={autoPreview} onAutoPreview={(on) => { saveAutoPreview(on); setAutoPreview(on); }} />
    </div>
    </HelpContext.Provider>
    </AiContext.Provider>
  );
}
