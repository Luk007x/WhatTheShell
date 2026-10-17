// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState, type ReactNode } from "react";
import { ApiError, errMsg, createRun, getRun } from "../api";
import { AiDialog, useAi } from "../ai/AiDialog";
import { stepFromEvents, stripOutputs, type Step } from "../ai/aiFlow";
import { HelpButton } from "../Help";
import { useDebounced } from "../hooks";
import { t } from "../i18n";
import { Icon } from "../icons";
import { Modal } from "../Modal";
import type { AskRequest, StepBlock, TerminalState } from "../model/run";
import type { Workflow } from "../types/workflow";
import { RunForm, VariableFields } from "./RunForm";
import { askedVariables, askValues, hasTerminal, initialValues, toOverrides, validate, withoutAsked, type FormValues } from "./runForm";
import { TerminalEnd, TerminalPane } from "./Terminal";
import { usePlanThenRun, useRun, type PlanThenRun, type Run } from "./useRun";

export function Problem({ error }: { error: unknown }) {
  const errors = error instanceof ApiError ? error.errors : [];
  return (
    <div role="alert" className="error">
      <p>{errMsg(error)}</p>
      {errors.length > 0 && <ul>{errors.map((e, i) => <li key={i}><code>{e.path}</code> {e.message}</li>)}</ul>}
    </div>
  );
}

/** Pause / single step / abort and the live status line of a run. */
export function RunControls({ run, testId = "run-status" }: { run: Run; testId?: string }) {
  const { view, running, paused } = run;
  return (
    <>
      <button onClick={() => run.control(paused ? "resume" : "pause")} disabled={!running}><Icon name={paused ? "play" : "pause"} />{paused ? t("run.resume") : t("run.pause")}</button>
      <button onClick={() => run.control("step")} disabled={!running}><Icon name="redo" />{t("run.step")}</button>
      <button className="btn--danger" onClick={() => run.control("abort")} disabled={!running}><Icon name="stop" />{t("run.abort")}</button>
      <span role="status" aria-live="polite" className="runstatus" data-testid={testId}>
        {t(`run.status.${view.status}`)}{view.message ? `: ${view.message}` : ""}{view.exitCode !== null && run.finished ? ` (${t("prev.exit")} ${view.exitCode})` : ""}
      </span>
    </>
  );
}

/** Error line, lost connection and step blocks with their output. */
export function RunOutput({ run, onSelect, extra }: { run: Run; onSelect?: (id: string) => void; extra?: (b: StepBlock) => ReactNode }) {
  const [dismissed, setDismissed] = useState<TerminalState | null>(null); // by identity: the next terminal_request makes a new object
  const term = run.view.terminal;
  return (
    <>
      {run.error !== null && <Problem error={run.error} />}
      {run.stopping && <p role="status">{t("run.stopping")}</p>}
      {run.lost && <p role="alert" className="error">{t("run.lost")} <button onClick={run.loadHistory}>{t("run.history")}</button></p>}
      {run.view.blocks.map((b) => (
        <details key={b.key} open className="block">
          <summary>
            <strong>{b.id}</strong>{" "}
            <code>{b.command}</code>{" "}
            {b.interactive && <span className="badge">{t("run.interactive")}</span>}
            <span className={`badge badge--${b.safety}`}>{t(`safety.${b.safety}`)}</span>
            {b.finish && <span className={`badge badge--${b.finish.ok ? "safe" : "dangerous"}`}>{b.finish.ok ? t("run.ok") : t("run.failed")}</span>}
            {b.skipped !== undefined && <span className="badge">{t("run.skipped")}</span>}
          </summary>
          {onSelect && <p><button className="btn--sm" onClick={() => onSelect(b.id)}>{t("run.select")}</button></p>}
          {b.lines.map((l, i) => (
            <pre key={i} className={l.stream} aria-label={t(`stream.${l.stream}`)}>{l.stream === "stderr" && <strong>{t("stream.stderr")}: </strong>}{l.text}</pre>
          ))}
          {b.messages.map((m, i) => <p key={i} role="note">{m}</p>)}
          {b.skipped !== undefined && <p className="muted">{b.skipped}</p>}
          {b.finish && (
            <p className="run-finish">
              <span>{t("prev.exit")}: {b.finish.exit_code ?? "-"} · {t("prev.duration")}: {b.finish.duration?.toFixed(2) ?? "-"} s</span>
              {extra?.(b)}
            </p>
          )}
        </details>
      ))}
      {term && term !== dismissed && !run.readOnly && (
        <TerminalPane key={term.stepId} runId={run.runId} terminal={term} transcript={run.transcript} onClose={run.terminalClosed}
          ended={run.view.terminalEnd?.stepId === term.stepId || run.view.status !== "running"} onDismiss={() => setDismissed(term)} />
      )}
      <TerminalEnd end={run.view.terminalEnd} closeCode={run.termClose} />
    </>
  );
}

/** Form of an `ask` step; remounted per request (`key`), so a re-ask starts from the server's `current`. Values are never stored. */
function AskForm({ ask, run }: { ask: AskRequest; run: Run }) {
  const entry = { variables: ask.fields };
  const [values, setValues] = useState<FormValues>(() => initialValues(entry, ask.current));
  const [shown, setShown] = useState(false); // errors only after the first submit
  const [left, setLeft] = useState(ask.timeout);
  useEffect(() => {
    if (ask.timeout === null) return;
    const end = Date.now() + ask.timeout * 1000;
    const id = setInterval(() => setLeft(Math.max(0, Math.ceil((end - Date.now()) / 1000))), 1000);
    return () => clearInterval(id);
  }, [ask.timeout]);
  const errors = validate(entry, values);
  const send = (button: string) => {
    setShown(true);
    if (Object.keys(errors).length === 0) run.answerAsk(askValues(entry, values), button);
  };
  const buttons = ask.buttons.length > 0 ? ask.buttons : ["OK"];
  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); send(buttons[0] ?? "OK"); }}>
      {ask.error && <p role="alert" className="error">{ask.error}</p>}
      {ask.text && <p style={{ whiteSpace: "pre-wrap" }}>{ask.text}</p>}
      <VariableFields prefix={`ask${ask.n}`} variables={ask.fields} values={values} errors={shown ? errors : {}} onValues={setValues} />
      {left !== null && <p className="muted" role="status">{t("ask.deadline", { n: left })}</p>}
      <div className="actions">
        <button type="button" className="btn--danger" disabled={run.answering} onClick={() => run.answerAsk({}, "", true)}>{t("ask.cancel")}</button>
        {buttons.map((b, i) => (
          <button key={`${i}-${b}`} type={i === 0 ? "submit" : "button"} className={i === 0 ? "btn--primary" : undefined} disabled={run.answering} onClick={i === 0 ? undefined : () => send(b)}>{b}</button>
        ))}
      </div>
    </form>
  );
}

/** Per-step confirmation (10.4) and `ask` dialog; kept outside hidden areas so they show in every mode. */
export function StepConfirm({ run }: { run: Run }) {
  const c = run.view.confirm;
  const ask = run.readOnly ? null : run.view.ask;
  return (
    <>
    <Modal open={ask !== null} title={ask?.title || t("ask.default")} onCancel={() => undefined /* Escape must not end the run by accident: only the explicit button */}>
      {ask && <AskForm key={ask.n} ask={ask} run={run} />}
    </Modal>
    <Modal open={c !== null} title={t("run.confirm.title")} onCancel={() => run.answer(false)}>
      {c && (
        <>
          <code className="cmd">{c.command}</code>
          <p>{t("cmd.safety")}: <span className={`badge badge--${c.safety}`}>{t(`safety.${c.safety}`)}</span></p>
          {c.reasons.length > 0 && <ul>{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
          <div className="actions">
            <button data-autofocus disabled={run.answering} onClick={() => run.answer(false)}>{t("run.reject")}</button>
            <button className={c.safety === "dangerous" ? "btn--danger" : "btn--primary"} disabled={run.answering} onClick={() => run.answer(true)}>{t("run.accept")}</button>
          </div>
        </>
      )}
    </Modal>
    </>
  );
}

/** Workflow confirmation before the real run (10.6): plan, highest class, working directory. */
export function RunDialog({ pr, children }: { pr: PlanThenRun; children?: ReactNode }) {
  const { prep } = pr;
  return (
    <Modal className="modal--tall" open={pr.open} title={t("run.dialog")} onCancel={pr.cancel}>
      {pr.error !== null && <Problem error={pr.error} />}
      {pr.changed && <p role="alert" className="error">{t("run.plan.changed")}</p>}
      {prep ? (
        <>
          <pre className="plan">{prep.plan}</pre>
          <p>{t("run.maxsafety")}: <span className={`badge badge--${prep.max_safety}`}>{t(`safety.${prep.max_safety}`)}</span></p>
          <p>{t("run.cwd.effective")}: <code>{prep.cwd ?? t("run.cwd.server")}</code></p>
        </>
      ) : pr.error === null && <p className="muted" role="status">{t("run.plan.loading")}</p>}
      {children}
      <div className="actions">
        <button data-autofocus onClick={pr.cancel}>{t("run.cancel")}</button>
        <button className="btn--primary" onClick={() => void pr.confirm()} disabled={prep === null || pr.busy}>{t("run.confirm")}</button>
      </div>
    </Modal>
  );
}

export function RunPanel({ wf, onCapture, onEvaluate, onSelectStep }: {
  wf: Workflow; onCapture: (id: string) => void; onEvaluate: (id: string) => void; onSelectStep: (id: string) => void;
}) {
  const run = useRun();
  const [plan, setPlan] = useState<string | null>(null);
  const [values, setValues] = useState<FormValues>({});
  const [cwd, setCwd] = useState("");
  const [transcript, setTranscript] = useState(false);
  const { enabled: aiOn } = useAi();
  const [diag, setDiag] = useState<Step | null>(null);
  const { view, running, runId } = run;
  const asked = askedVariables(wf);
  const all = wf.variables ?? {};
  const entry = withoutAsked({ variables: all }, asked);

  const request = (dry: boolean) => createRun({ document: wf, variables: toOverrides(entry, values), cwd: cwd.trim() === "" ? null : cwd.trim(), dry_run: dry, ...(transcript ? { transcript } : {}) }); // omitted when off: the default
  const pr = usePlanThenRun(run, request, transcript);

  // inputs changed while the dialog is open: drop the old plan, fetch the new one debounced
  const dryKey = useDebounced(pr.open ? JSON.stringify([values, cwd, wf, transcript]) : "", 300); // string: stable across renders
  useEffect(() => { if (pr.open && dryKey !== "") pr.refresh(); }, [dryKey]); // pr.refresh reads the latest inputs
  const change = (next: () => void) => { next(); pr.invalidate(); };

  const trockenlauf = () => {
    run.setError(null);
    request(true).then((r) => setPlan(r.plan), (e: unknown) => { setPlan(null); run.setError(e); });
  };

  const diagnose = (stepId: string) => {
    if (runId) getRun(runId).then((r) => setDiag(stepFromEvents(r.events, stepId)), run.setError);
  };

  return (
    <section aria-label={t("output.title")} className="run">
      <div className="toolbar">
        <h2>{t("output.title")}</h2>
        <HelpButton section="run" topic={t("output.title")} />
        <button onClick={trockenlauf} disabled={running} aria-describedby="run-help">{t("run.dry")}</button>
        <button className="btn--primary" disabled={running} onClick={() => { setValues(initialValues(entry, values)); setPlan(null); pr.plan(); }}>
          <Icon name="play" filled />{t("run.execute")}
        </button>
        <RunControls run={run} />
      </div>
      <p className="muted" id="run-help">{t("run.dry.help")} {t("run.step.help")}{view.blocks.length > 0 && ` ${t("run.capture.help")} ${t("run.evaluate.help")}`}</p>
      {plan !== null && <><h3>{t("run.plan")}</h3><pre className="plan" data-testid="plan">{plan}</pre></>}
      {view.status === "idle" && plan === null && <p className="muted">{t("output.placeholder")}</p>}
      <RunOutput run={run} onSelect={onSelectStep} extra={(b) => (
        <>
          <button className="btn--sm" title={t("run.capture.help")} onClick={() => onCapture(b.id)}>{t("run.capture")}</button>
          <button className="btn--sm" title={t("run.evaluate.help")} onClick={() => onEvaluate(b.id)}>{t("run.evaluate")}</button>
          {aiOn && b.finish && !b.finish.ok && <button className="btn--sm" onClick={() => diagnose(b.id)}>{t("ai.diagnose")}</button>}
        </>
      )} />
      <StepConfirm run={run} />

      {diag && <AiDialog task="diagnose" title={t("ai.diagnose")} diagnose onClose={() => setDiag(null)}
        build={(include) => ({ step: stripOutputs(diag, include), include_output: include })} />}

      <RunDialog pr={pr}>
        <RunForm prefix="rv" hidden={Object.keys(all).length - Object.keys(entry.variables).length} variables={entry.variables} values={values} cwd={cwd}
          onValues={(v) => change(() => setValues(v))} onCwd={(c) => change(() => setCwd(c))}
          transcript={hasTerminal(wf.steps) ? transcript : undefined} onTranscript={(on) => change(() => setTranscript(on))} />
      </RunDialog>
    </section>
  );
}
