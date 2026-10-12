// SPDX-License-Identifier: AGPL-3.0-or-later
// Three stages (F-30): data preview -> waiting (abortable) -> result as diff for approval. Nothing is applied or run automatically.
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { aiApply, aiTask, ApiError, errMsg } from "../api";
import { t } from "../i18n";
import { Modal } from "../Modal";
import type { AiBody, AiPreview, AiResult, AiTaskName } from "../types/api";
import { canApply, diffLines } from "./aiFlow";

/** `enabled` mirrors `ai.enabled`; `openSettings` is used by the 403 hint. Provided by App. */
export const AiContext = createContext<{ enabled: boolean; openSettings: () => void }>({ enabled: false, openSettings: () => undefined });
export const useAi = () => useContext(AiContext);

function Failure({ error, onSettings }: { error: unknown; onSettings: () => void }) {
  const status = error instanceof ApiError ? error.status : 0;
  return (
    <div role="alert" className="error">
      {status === 403 ? <p>{t("ai.err.disabled")} <button className="linkbtn" onClick={onSettings}>{t("ai.err.settings")}</button></p>
        : status === 429 ? <p>{t("ai.err.busy")}</p>
        : <p>{status === 502 ? `${t("ai.err.provider")}: ` : ""}{errMsg(error)}</p>}
    </div>
  );
}

/** Mount to open. `build(include)` yields the request body; `diagnose` adds the output checkbox. */
export function AiDialog({ task, build, title, diagnose = false, onClose, onApplied }: {
  task: AiTaskName; build: (includeOutput: boolean) => AiBody; title: string; diagnose?: boolean;
  onClose: () => void; onApplied?: (result: AiResult) => void;
}) {
  const { openSettings } = useAi();
  const [include, setInclude] = useState(false);
  const [preview, setPreview] = useState<AiPreview | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [result, setResult] = useState<AiResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const ctrl = useRef<AbortController | null>(null);
  const buildRef = useRef(build);
  buildRef.current = build;

  const run = <T,>(call: (signal: AbortSignal) => Promise<T>, done: (v: T) => void) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setError(null);
    call(c.signal).then((v) => { if (!c.signal.aborted) done(v); }, (e: unknown) => { if (!c.signal.aborted) setError(e); }).finally(() => { if (ctrl.current === c) setWaiting(false); });
  };
  useEffect(() => {
    setPreview(null);
    run((s) => aiTask(task, { ...buildRef.current(include), send: false }, s), setPreview);
    return () => ctrl.current?.abort();
  }, [task, include]);

  const send = () => { setWaiting(true); run((s) => aiTask(task, { ...build(include), send: true }, s), setResult); };
  const abort = () => { ctrl.current?.abort(); setWaiting(false); };
  const apply = () => {
    if (!result || !canApply(result)) return;
    const finish = () => { onApplied?.(result); onClose(); };
    if (result.kind === "module" && result.target) run(() => aiApply("module", result.raw, result.target ?? ""), finish);
    else finish(); // workflows are loaded into the editor unsaved by the caller
  };
  const settings = () => { onClose(); openSettings(); };

  return (
    <Modal open title={title} onCancel={() => { ctrl.current?.abort(); onClose(); }}>
      {error !== null && <Failure error={error} onSettings={settings} />}
      {result === null && !waiting && (
        <>
          <p>{t("ai.preview.intro")}</p>
          {diagnose && <label><input type="checkbox" checked={include} onChange={(e) => setInclude(e.target.checked)} /> {t("ai.include")}</label>}
          {preview ? (
            <>
              <p role="status">{t("ai.chars", { n: preview.chars })}</p>
              <h3>System</h3><pre className="ai-pre" tabIndex={0} aria-label="System">{preview.prompt.system}</pre>
              <h3>User</h3><pre className="ai-pre" tabIndex={0} aria-label="User">{preview.prompt.user}</pre>
            </>
          ) : error === null && <p role="status">{t("catalog.loading")}</p>}
          <div className="actions">
            <button data-autofocus onClick={onClose}>{t("run.cancel")}</button>
            <button onClick={send} disabled={!preview}>{t("ai.send")}</button>
          </div>
        </>
      )}
      {waiting && (
        <>
          <p role="status">{t("ai.waiting")}</p>
          <div className="actions"><button data-autofocus onClick={abort}>{t("ai.abort")}</button></div>
        </>
      )}
      {result !== null && (
        <>
          {result.kind === "text" ? <pre className="ai-pre" tabIndex={0} data-testid="ai-text">{result.raw}</pre> : (
            <>
              <p role="status" data-testid="ai-valid">{result.valid ? t("ai.valid.yes") : t("ai.valid.no")}</p>
              {result.errors.length > 0 && <ul role="alert" className="errors" data-testid="ai-errors">{result.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
              <h3>{t("ai.diff")}</h3>
              <pre className="ai-pre diff" tabIndex={0} data-testid="ai-diff" aria-label={t("ai.diff")}>
                {diffLines(result.diff).map((l, i) => (
                  <span key={i} className={`diff-${l.kind}`}>{l.kind === "add" || l.kind === "del" ? <span className="sr-only">{t(`ai.diff.${l.kind}`)}: </span> : null}{l.text}{"\n"}</span>
                ))}
              </pre>
              {result.kind === "workflow" && <p className="hint">{t("ai.unsaved")}</p>}
            </>
          )}
          <div className="actions">
            {result.kind === "text" ? <button data-autofocus onClick={onClose}>{t("settings.close")}</button> : (
              <>
                <button data-autofocus onClick={onClose}>{t("ai.discard")}</button>
                <button onClick={apply} disabled={!canApply(result)}>{t("ai.apply")}</button>
              </>
            )}
          </div>
        </>
      )}
    </Modal>
  );
}
