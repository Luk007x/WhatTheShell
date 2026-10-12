// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { ApiError, confirmRun, errMsg, controlRun, createRun, getRun, startRun, wsUrl } from "../api";
import { useDebounced } from "../hooks";
import { t } from "../i18n";
import { Modal } from "../Modal";
import { initialRun, reduceEvents, type RunView } from "../model/run";
import type { RunCreated, RunEvent } from "../types/api";
import type { Workflow } from "../types/workflow";

type Action = { kind: "event"; ev: RunEvent } | { kind: "reset"; events?: RunEvent[] } | { kind: "clearConfirm" };
const reducer = (s: RunView, a: Action): RunView =>
  a.kind === "event" ? reduceEvents(s, a.ev) : a.kind === "reset" ? (a.events ?? []).reduce(reduceEvents, initialRun) : { ...s, confirm: null };

const finishedStatus = (s: RunView) => s.status === "success" || s.status === "failed" || s.status === "aborted";

function convert(type: string | undefined, text: string): unknown {
  if ((type === "int" || type === "float") && text.trim() !== "" && !Number.isNaN(Number(text))) return Number(text);
  if (type === "bool") return text === "true";
  return text;
}

function Problem({ error }: { error: unknown }) {
  const errors = error instanceof ApiError ? error.errors : [];
  return (
    <div role="alert" className="error">
      <p>{errMsg(error)}</p>
      {errors.length > 0 && <ul>{errors.map((e, i) => <li key={i}><code>{e.path}</code> {e.message}</li>)}</ul>}
    </div>
  );
}

export function RunPanel({ wf, onCapture, onEvaluate, onSelectStep }: {
  wf: Workflow; onCapture: (id: string) => void; onEvaluate: (id: string) => void; onSelectStep: (id: string) => void;
}) {
  const [view, dispatch] = useReducer(reducer, initialRun);
  const [runId, setRunId] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [lost, setLost] = useState(false);
  const [plan, setPlan] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [dialog, setDialog] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [cwd, setCwd] = useState("");
  const [prep, setPrep] = useState<RunCreated | null>(null);
  const [prepError, setPrepError] = useState<unknown>(null);
  const ws = useRef<WebSocket | null>(null);
  const viewRef = useRef(view);
  viewRef.current = view;
  const running = view.status === "running";

  const request = useCallback((dry: boolean) => ({
    document: wf,
    variables: Object.fromEntries(Object.entries(values).filter(([, v]) => v !== "").map(([k, v]) => [k, convert(wf.variables?.[k]?.type, v)])),
    cwd: cwd.trim() === "" ? null : cwd.trim(),
    dry_run: dry,
  }), [wf, values, cwd]);

  const dry = useDebounced(dialog ? JSON.stringify(request(true)) : "", 300);
  useEffect(() => {
    if (!dialog || dry === "") return;
    let stale = false;
    createRun(JSON.parse(dry) as ReturnType<typeof request>) // own JSON.stringify above
      .then((r) => { if (!stale) { setPrep(r); setPrepError(null); } })
      .catch((e: unknown) => { if (!stale) { setPrep(null); setPrepError(e); } });
    return () => { stale = true; };
  }, [dry, dialog]);

  useEffect(() => () => ws.current?.close(), []);

  const trockenlauf = () => {
    setError(null);
    createRun({ document: wf, variables: {}, cwd: null, dry_run: true }).then((r) => setPlan(r.plan), (e: unknown) => { setPlan(null); setError(e); });
  };

  const connect = (id: string) => {
    ws.current?.close();
    const sock = new WebSocket(wsUrl(`/ws/runs/${encodeURIComponent(id)}`));
    ws.current = sock;
    sock.onmessage = (m) => {
      try {
        const ev: unknown = JSON.parse(String(m.data));
        if (ev && typeof ev === "object" && "type" in ev && typeof ev.type === "string") dispatch({ kind: "event", ev: ev as RunEvent }); // shape checked above
      } catch (e) {
        setError(e);
      }
    };
    sock.onclose = () => { if (ws.current === sock && !finishedStatus(viewRef.current)) setLost(true); };
  };

  const execute = async () => {
    let id: string;
    try {
      id = (await createRun(request(false))).run_id;
    } catch (e) {
      setPrepError(e); // dialog is still open
      return;
    }
    setDialog(false);
    setPlan(null);
    setError(null);
    setLost(false);
    setPaused(false);
    setRunId(id);
    dispatch({ kind: "reset" });
    connect(id);
    try {
      await startRun(id);
    } catch (e) {
      setError(e); // dialog is closed: show the error in the visible error line
    }
  };

  const control = (action: "abort" | "pause" | "resume" | "step") => {
    if (!runId) return;
    controlRun(runId, action).then(() => { if (action === "pause") setPaused(true); if (action === "resume") setPaused(false); }, setError);
  };

  const answer = (ok: boolean) => {
    const c = view.confirm;
    if (!c || !runId) return;
    dispatch({ kind: "clearConfirm" });
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ type: "confirm", step_id: c.step_id, ok }));
    else confirmRun(runId, c.step_id, ok).catch(setError);
  };

  const loadHistory = () => {
    if (!runId) return;
    getRun(runId).then((r) => { dispatch({ kind: "reset", events: r.events }); setLost(false); }, setError);
  };

  const vars = Object.entries(wf.variables ?? {});
  return (
    <section aria-label={t("output.title")} className="run">
      <div className="toolbar">
        <h2>{t("output.title")}</h2>
        <button onClick={trockenlauf} disabled={running}>{t("run.dry")}</button>
        <button onClick={() => { setPrep(null); setPrepError(null); setDialog(true); }} disabled={running}>{t("run.execute")}</button>
        <button onClick={() => control(paused ? "resume" : "pause")} disabled={!running}>{paused ? t("run.resume") : t("run.pause")}</button>
        <button onClick={() => control("step")} disabled={!running}>{t("run.step")}</button>
        <button onClick={() => control("abort")} disabled={!running}>{t("run.abort")}</button>
        <span role="status" className="runstatus" data-testid="run-status">
          {t(`run.status.${view.status}`)}{view.message ? `: ${view.message}` : ""}{view.exitCode !== null && finishedStatus(view) ? ` (${t("prev.exit")} ${view.exitCode})` : ""}
        </span>
      </div>
      {error !== null && <Problem error={error} />}
      {lost && <p role="alert" className="error">{t("run.lost")} <button onClick={loadHistory}>{t("run.history")}</button></p>}
      {plan !== null && <><h3>{t("run.plan")}</h3><pre className="plan" data-testid="plan">{plan}</pre></>}
      {view.status === "idle" && plan === null && <p className="muted">{t("output.placeholder")}</p>}
      {view.blocks.map((b) => (
        <details key={b.key} open className="block">
          <summary>
            <strong>{b.id}</strong>{" "}
            <code>{b.command}</code>{" "}
            <span className={`dot ${b.safety}`} aria-hidden="true" /> {t(`safety.${b.safety}`)}
            {b.finish && <strong> · {b.finish.ok ? t("run.ok") : t("run.failed")}</strong>}
            {b.skipped !== undefined && <strong> · {t("run.skipped")}</strong>}
          </summary>
          <p><button onClick={() => onSelectStep(b.id)}>{t("run.select")}</button></p>
          {b.lines.map((l, i) => (
            <pre key={i} className={l.stream} aria-label={t(`stream.${l.stream}`)}>{l.stream === "stderr" && <strong>{t("stream.stderr")}: </strong>}{l.text}</pre>
          ))}
          {b.messages.map((m, i) => <p key={i} role="note">{m}</p>)}
          {b.skipped !== undefined && <p className="muted">{b.skipped}</p>}
          {b.finish && (
            <p>
              {t("prev.exit")}: {b.finish.exit_code ?? "-"} · {t("prev.duration")}: {b.finish.duration?.toFixed(2) ?? "-"} s
              {" "}<button onClick={() => onCapture(b.id)}>{t("run.capture")}</button>{" "}
              <button onClick={() => onEvaluate(b.id)}>{t("run.evaluate")}</button>
            </p>
          )}
        </details>
      ))}

      <Modal open={dialog} title={t("run.dialog")} onCancel={() => setDialog(false)}>
        {prepError !== null && <Problem error={prepError} />}
        {prep && (
          <>
            <pre className="plan">{prep.plan}</pre>
            <p>{t("run.maxsafety")}: <span className={`dot ${prep.max_safety}`} aria-hidden="true" /> <strong>{t(`safety.${prep.max_safety}`)}</strong></p>
            <p>{t("run.cwd.effective")}: <code>{prep.cwd ?? t("run.cwd.server")}</code></p>
          </>
        )}
        {vars.map(([name, v]) => (
          <div className="field" key={name}>
            <label htmlFor={`rv-${name}`}>{v.label ?? name}{v.required && <span className="req"> *</span>} <small className="muted">{name}{v.default !== undefined ? ` (${String(v.default)})` : ""}</small></label>
            <input id={`rv-${name}`} value={values[name] ?? ""} onChange={(e) => setValues({ ...values, [name]: e.target.value })} />
          </div>
        ))}
        <div className="field">
          <label htmlFor="run-cwd">{t("step.cwd")}</label>
          <input id="run-cwd" value={cwd} placeholder={t("run.cwd.placeholder")} onChange={(e) => setCwd(e.target.value)} />
        </div>
        <div className="actions">
          <button data-autofocus onClick={() => setDialog(false)}>{t("run.cancel")}</button>
          <button onClick={() => void execute()} disabled={prep === null}>{t("run.confirm")}</button>
        </div>
      </Modal>

      <Modal open={view.confirm !== null} title={t("run.confirm.title")} onCancel={() => answer(false)}>
        {view.confirm && (
          <>
            <code className="cmd">{view.confirm.command}</code>
            <p><span className={`dot ${view.confirm.safety}`} aria-hidden="true" /> {t("cmd.safety")}: <strong>{t(`safety.${view.confirm.safety}`)}</strong></p>
            {view.confirm.reasons.length > 0 && <ul>{view.confirm.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
            <div className="actions">
              <button data-autofocus onClick={() => answer(false)}>{t("run.reject")}</button>
              <button onClick={() => answer(true)}>{t("run.accept")}</button>
            </div>
          </>
        )}
      </Modal>
    </section>
  );
}
