// SPDX-License-Identifier: AGPL-3.0-or-later
// Mode "Ausführen": workflow library, input form from `variables`, confirmation, live output, recent runs.
// Stays mounted while another mode is shown (`active` false), so a running run keeps its socket and dialogs.
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getWorkflow, listRuns, listWorkflows, runWorkflowById } from "../api";
import { AcceptButton, Library } from "../files/Library";
import { getLang, t } from "../i18n";
import { needsAccept } from "../files/libraryImport";
import { Icon } from "../icons";
import type { RunListItem, WorkflowListItem } from "../types/api";
import type { Workflow } from "../types/workflow";
import { RunForm } from "./RunForm";
import { askedVariables, hasTerminal, initialValues, storable, toOverrides, validate, withoutAsked, type FieldError, type FormValues } from "./runForm";
import { Problem, RunControls, RunDialog, RunOutput, StepConfirm } from "./RunPanel";
import { usePlanThenRun, useRun } from "./useRun";

const STATUS_CLASS: Record<RunListItem["status"], string> = { created: "", running: "", success: "badge--safe", failed: "badge--dangerous", aborted: "badge--caution" };

type Stored = { values: unknown; cwd: string };
const storeKey = (id: string) => `wts.runvalues.${id}`;
function loadStored(id: string): Stored {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(storeKey(id)) ?? "null");
    if (raw && typeof raw === "object" && "values" in raw) return { values: raw.values, cwd: "cwd" in raw && typeof raw.cwd === "string" ? raw.cwd : "" };
  } catch { /* unreadable: defaults */ }
  return { values: null, cwd: "" };
}

export function RunView({ active, onOpenInEditor }: { active: boolean; onOpenInEditor: (doc: Workflow, id: string) => void }) {
  const [items, setItems] = useState<WorkflowListItem[]>([]);
  const [libError, setLibError] = useState<unknown>(null);
  const [selId, setSelId] = useState<string | null>(null);
  const [values, setValues] = useState<FormValues>({});
  const [cwd, setCwd] = useState("");
  const [transcript, setTranscript] = useState(false);
  const [withTerminal, setWithTerminal] = useState(false); // the picked workflow has a terminal step
  const [errors, setErrors] = useState<Record<string, FieldError>>({});
  const [formError, setFormError] = useState<unknown>(null);
  const [plan, setPlan] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [ranId, setRanId] = useState<string | null>(null); // workflow of the run started here
  const run = useRun();
  const out = useRef<HTMLDivElement>(null);
  const [loadedId, setLoadedId] = useState<string | null>(null); // workflow whose document (asked variables) has arrived
  const [asked, setAsked] = useState<ReadonlySet<string>>(new Set()); // variables an ask step collects in the run
  const picked = items.find((x) => x.id === selId) ?? null;
  const loaded = loadedId !== null && loadedId === selId;
  const entry = picked && { ...picked, ...withoutAsked(picked, asked) };

  const body = (dry: boolean) => ({ variables: entry ? toOverrides(entry, values) : {}, cwd: cwd.trim() === "" ? null : cwd.trim(), dry_run: dry, ...(transcript ? { transcript } : {}) }); // omitted when off: the default
  const pr = usePlanThenRun(run, (dry) => {
    if (!entry) return Promise.reject(new Error(t("runview.pick")));
    if (!dry) setRanId(entry.id);
    return runWorkflowById(entry.id, body(dry)).catch((e: unknown) => {
      if (e instanceof ApiError && e.error === "integrity") reload(); // the list shows the badge and the accept button
      throw e;
    });
  }, transcript);

  const reloadRuns = useCallback(() => { listRuns().then(setRuns, setLibError); }, []);
  const reload = useCallback(() => {
    listWorkflows().then((x) => { setItems(x); setLibError(null); }, setLibError);
    reloadRuns();
  }, [reloadRuns]);
  useEffect(() => { // the server watches the folders; reload when the user comes back instead of polling
    if (!active) return;
    reload();
    window.addEventListener("focus", reload);
    return () => window.removeEventListener("focus", reload);
  }, [active, reload]);
  useEffect(() => { if (run.runId) reloadRuns(); }, [run.runId, run.finished, reloadRuns]);
  useEffect(() => { if (run.running && out.current) out.current.scrollTop = out.current.scrollHeight; }, [run.view, run.running]);

  const save = (v: FormValues, c: string) => {
    if (!entry) return;
    try { localStorage.setItem(storeKey(entry.id), JSON.stringify({ values: storable(entry, v), cwd: c })); } catch { /* storage unavailable: values last for this session */ }
  };
  const pick = (x: WorkflowListItem) => {
    const s = loadStored(x.id);
    setSelId(x.id); setValues(initialValues(x, s.values)); setCwd(s.cwd); setErrors({}); setFormError(null); setPlan(null); setTranscript(false); setWithTerminal(false);
    setAsked(new Set()); setLoadedId(null);
    getWorkflow(x.id).then((r) => { setWithTerminal(hasTerminal(r.document.steps)); setAsked(askedVariables(r.document)); setLoadedId(x.id); }, setFormError);
  };
  const checked = (): boolean => {
    if (!entry || !loaded) return false;
    const e = validate(entry, values);
    setErrors(e);
    setFormError(null);
    return Object.keys(e).length === 0;
  };
  const dryRun = () => {
    if (!entry || !checked()) return;
    runWorkflowById(entry.id, body(true)).then((r) => setPlan(r.plan), (e: unknown) => { setPlan(null); setFormError(e); });
  };
  const execute = () => { if (checked()) { setPlan(null); pr.plan(); } };
  const openInEditor = (id: string) => { getWorkflow(id).then((r) => onOpenInEditor(r.document, r.id), setFormError); };

  const done = run.finished && !run.readOnly && ranId !== null;
  return (
    <>
      <main id={active ? "main" : undefined} tabIndex={-1} className="app-main run-main" hidden={!active}>
        <section className="panel" aria-labelledby="lib-h">
          <div className="panel__header">
            <h2 id="lib-h">{t("lib.title")}</h2>
            <button className="btn--sm" onClick={reload}>{t("lib.refresh")}</button>
          </div>
          {libError !== null && <Problem error={libError} />}
          <Library items={items} selected={selId} onPick={pick} onChanged={(x) => { reload(); if (x) pick(x); }} />
        </section>
        <section className="panel" aria-labelledby="runform-h">
          <div className="panel__header"><h2 id="runform-h">{t("runview.form")}</h2></div>
          <div className="panel__body">
            {!entry && <p className="muted">{t("runview.pick")}</p>}
            {entry && (
              <form className="runform" noValidate aria-label={entry.name} onSubmit={(e) => { e.preventDefault(); execute(); }}>
                <h3>{entry.name}</h3>
                {entry.description && <p className="hint">{entry.description}</p>}
                <RunForm prefix="rf" hidden={Object.keys(picked?.variables ?? {}).length - Object.keys(entry.variables).length} variables={entry.variables} values={values} errors={errors} cwd={cwd}
                  onValues={(v) => { setValues(v); save(v, cwd); }} onCwd={(c) => { setCwd(c); save(values, c); }}
                  transcript={withTerminal ? transcript : undefined} onTranscript={setTranscript} />
                {picked && needsAccept(picked) && (
                  <p role="alert" className="error">{t("lib.integrity.refused")} <AcceptButton id={picked.id} onDone={() => { setFormError(null); reload(); }} onError={setFormError} /></p>
                )}
                {formError !== null && <Problem error={formError} />}
                <div className="tb-group">
                  <button type="button" onClick={dryRun} disabled={!loaded}>{t("run.dry")}</button>
                  <button type="submit" className="btn--primary" disabled={run.running || !loaded}><Icon name="play" filled />{t("run.execute")}</button>
                </div>
              </form>
            )}
            <h3 id="runs-h">{t("runview.recent")}</h3>
            {runs.length === 0 && <p className="muted">{t("runview.norun")}</p>}
            <ul className="tools" aria-labelledby="runs-h">
              {runs.map((r) => (
                <li key={r.run_id}>
                  <button className="tool" aria-current={run.runId === r.run_id} onClick={() => run.show(r.run_id)}>
                    <span className="name">{r.workflow_name}</span>
                    <span className="lib-meta">
                      <span className={`badge ${STATUS_CLASS[r.status]}`}>{t(`run.status.${r.status}`)}</span>
                      <span className="muted">{r.started ? new Date(r.started).toLocaleString(getLang()) : "-"} · {t("prev.exit")} {r.exit_code ?? "-"}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>
      <footer className="app-footer run-footer" hidden={!active}>
        <section aria-label={t("output.title")} className="run">
          <div className="toolbar">
            <h2>{t("output.title")}</h2>
            <RunControls run={run} testId="runview-status" />
            {done && <button onClick={execute} disabled={ranId !== selId || run.running || !loaded}>{t("runview.again")}</button>}
            {done && <button onClick={() => openInEditor(ranId)}>{t("runview.editor")}</button>}
          </div>
          <div className="run-out" ref={out}>
            {plan !== null && <><h3>{t("run.plan")}</h3><pre className="plan" data-testid="runview-plan">{plan}</pre></>}
            {run.view.status === "idle" && plan === null && <p className="muted">{t("output.placeholder")}</p>}
            <RunOutput run={run} />
          </div>
        </section>
      </footer>
      {/* dialogs outside the hidden areas: a step waiting for confirmation shows in every mode */}
      <RunDialog pr={pr} />
      <StepConfirm run={run} />
    </>
  );
}
