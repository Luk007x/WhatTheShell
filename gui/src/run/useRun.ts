// SPDX-License-Identifier: AGPL-3.0-or-later
// Run state shared by the editor's run panel and the run view: events over WebSocket, control, step confirmation,
// and the 10.6 flow "dry run → confirm the plan → real run".
import { useEffect, useReducer, useRef, useState } from "react";
import { confirmRun, controlRun, getRun, startRun, wsUrl } from "../api";
import { initialRun, reduceEvents, type RunView } from "../model/run";
import type { RunAction, RunCreated, RunEvent } from "../types/api";

type Action = { kind: "event"; ev: RunEvent } | { kind: "reset"; events?: RunEvent[] } | { kind: "clearConfirm"; stepId: string };
const reducer = (s: RunView, a: Action): RunView => {
  switch (a.kind) {
    case "event": return reduceEvents(s, a.ev);
    case "reset": return (a.events ?? []).reduce(reduceEvents, initialRun);
    case "clearConfirm": return s.confirm?.step_id === a.stepId ? { ...s, confirm: null } : s; // a newer request stays
  }
};

export const isFinished = (s: RunView) => s.status === "success" || s.status === "failed" || s.status === "aborted";
const finishedStatus = (status: string) => status === "success" || status === "failed" || status === "aborted";

export function useRun() {
  const [view, dispatch] = useReducer(reducer, initialRun);
  const [runId, setRunId] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [lost, setLost] = useState(false);
  const [readOnly, setReadOnly] = useState(false);
  const [answering, setAnswering] = useState(false);
  const [transcript, setTranscript] = useState(false); // option of the run being followed
  const [termClose, setTermClose] = useState<number | null>(null); // abnormal close code of the terminal socket
  const [error, setError] = useState<unknown>(null);
  const ws = useRef<WebSocket | null>(null);
  const viewRef = useRef(view);
  viewRef.current = view;
  const seq = useRef(0); // bumped by every switch of the shown run; late answers of older requests are dropped

  useEffect(() => () => ws.current?.close(), []);

  const disconnect = () => { const s = ws.current; ws.current = null; s?.close(); };
  /** The server replays the history first, then streams live events. */
  const connect = (id: string) => {
    disconnect();
    const sock = new WebSocket(wsUrl(`/ws/runs/${encodeURIComponent(id)}`));
    ws.current = sock;
    sock.onmessage = (m) => {
      if (ws.current !== sock) return;
      try {
        const ev: unknown = JSON.parse(String(m.data));
        if (ev && typeof ev === "object" && "type" in ev && typeof ev.type === "string") dispatch({ kind: "event", ev: ev as RunEvent }); // shape checked above
      } catch (e) {
        setError(e);
      }
    };
    sock.onclose = () => { if (ws.current === sock && !isFinished(viewRef.current)) setLost(true); };
  };

  const select = (id: string, ro: boolean) => {
    setError(null); setTermClose(null); setLost(false); setPaused(false); setReadOnly(ro); setRunId(id);
    return ++seq.current;
  };

  /** Follow and start a run created with `POST /api/runs` or `/api/workflows/{id}/run` (dry_run false). */
  const launch = async (id: string, withTranscript = false) => {
    const n = select(id, false);
    setTranscript(withTranscript);
    dispatch({ kind: "reset" });
    connect(id);
    try {
      await startRun(id);
    } catch (e) {
      if (n === seq.current) setError(e);
    }
  };

  /** Show the recorded events of a run without controls. */
  const show = (id: string) => {
    const n = select(id, true);
    disconnect();
    getRun(id).then((r) => { if (n === seq.current) dispatch({ kind: "reset", events: r.events }); }, (e: unknown) => { if (n === seq.current) setError(e); });
  };

  const control = (action: RunAction) => {
    if (!runId) return;
    controlRun(runId, action).then(() => { if (action === "pause") setPaused(true); if (action === "resume") setPaused(false); }, setError);
  };

  /** Answer a confirm_request; the dialog closes only once the answer went out. */
  const answer = (ok: boolean) => {
    const c = view.confirm;
    if (!c || !runId || answering) return;
    const sock = ws.current;
    if (sock?.readyState === WebSocket.OPEN) {
      try {
        sock.send(JSON.stringify({ type: "confirm", step_id: c.step_id, ok }));
        dispatch({ kind: "clearConfirm", stepId: c.step_id });
      } catch (e) {
        setError(e);
      }
      return;
    }
    setAnswering(true);
    confirmRun(runId, c.step_id, ok)
      .then(() => dispatch({ kind: "clearConfirm", stepId: c.step_id }), setError)
      .finally(() => setAnswering(false));
  };

  /** After a lost connection: reload the history; a run that is still going is followed again. */
  const loadHistory = () => {
    if (!runId) return;
    const id = runId;
    const n = ++seq.current;
    getRun(id).then((r) => {
      if (n !== seq.current) return;
      setLost(false);
      if (finishedStatus(r.status)) dispatch({ kind: "reset", events: r.events });
      else { dispatch({ kind: "reset" }); connect(id); } // the socket replays the history itself
    }, (e: unknown) => { if (n === seq.current) setError(e); });
  };

  return {
    view, runId, paused, lost, readOnly, answering, error, setError, transcript, termClose,
    terminalClosed: setTermClose,
    running: view.status === "running" && !readOnly,
    finished: isFinished(view),
    launch, show, control, answer, loadHistory,
  };
}

export type Run = ReturnType<typeof useRun>;

/**
 * 10.6: dry run → dialog with plan → real request. The real answer's plan must equal the confirmed one;
 * otherwise the dialog shows the new plan and nothing starts.
 */
export function usePlanThenRun(run: Run, create: (dry: boolean) => Promise<RunCreated>, transcript = false) {
  const [open, setOpen] = useState(false);
  const [prep, setPrep] = useState<RunCreated | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [changed, setChanged] = useState(false);
  const createRef = useRef(create);
  createRef.current = create;
  const transcriptRef = useRef(transcript);
  transcriptRef.current = transcript;
  const seq = useRef(0);

  /** Forget the shown plan (inputs changed); `refresh` brings the new one. */
  const invalidate = () => { seq.current++; setPrep(null); setError(null); setChanged(false); };
  const refresh = () => {
    const n = ++seq.current;
    createRef.current(true).then((r) => { if (n === seq.current) { setPrep(r); setError(null); } }, (e: unknown) => { if (n === seq.current) { setPrep(null); setError(e); } });
  };
  const plan = () => { invalidate(); setOpen(true); refresh(); };
  const cancel = () => { seq.current++; setOpen(false); };

  const confirm = async () => {
    const confirmed = prep;
    if (!confirmed || busy) return;
    const n = ++seq.current;
    setBusy(true);
    try {
      const real = await createRef.current(false);
      if (n !== seq.current) return;
      if (real.plan !== confirmed.plan || real.max_safety !== confirmed.max_safety) { setPrep(real); setChanged(true); return; }
      setOpen(false);
      setChanged(false);
      await run.launch(real.run_id, transcriptRef.current);
    } catch (e) {
      if (n === seq.current) setError(e); // dialog is still open
    } finally {
      setBusy(false);
    }
  };

  return { open, prep, error, busy, changed, plan, refresh, invalidate, cancel, confirm };
}
export type PlanThenRun = ReturnType<typeof usePlanThenRun>;
