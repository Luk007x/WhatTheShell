// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState, type MutableRefObject } from "react";
import { ApiError, deleteWorkflow, getWorkflow, listWorkflows, putWorkflow } from "../api";
import { AiDialog, useAi } from "../ai/AiDialog";
import { t } from "../i18n";
import { parseRaw } from "../modules/moduleForm";
import { FILE_ID_PATTERN, slugify } from "../model/files";
import { Modal } from "../Modal";
import { Library } from "./Library";
import type { WorkflowListItem } from "../types/api";
import type { Workflow } from "../types/workflow";

type Mode = null | "open" | "save" | "draft";

export function FileMenu({ wf, fileId, dirty, onLoad, onSaved, onDeleted, onNew, onDraft, saveRef }: {
  wf: Workflow; fileId: string | null; dirty: boolean;
  onLoad: (doc: Workflow, id: string) => void; onSaved: (id: string) => void; onDeleted: (id: string) => void; onNew: () => void;
  /** An AI draft: load it unsaved (the user saves it explicitly). */
  onDraft: (doc: Workflow) => void;
  /** Set to the "Save" action so a shortcut outside can trigger it. */
  saveRef?: MutableRefObject<(() => void) | null>;
}) {
  const { enabled: aiOn } = useAi();
  const [desc, setDesc] = useState("");
  const [draftName, setDraftName] = useState("");
  const [asking, setAsking] = useState(false);
  const [mode, setMode] = useState<Mode>(null);
  const [list, setList] = useState<WorkflowListItem[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [id, setId] = useState("");
  const [loaded, setLoaded] = useState(false); // saving waits for the list (overwrite check)
  const discard = () => !dirty || window.confirm(t("file.discard"));
  const refresh = () => listWorkflows().then(setList, setError).finally(() => setLoaded(true));

  const open = (m: Exclude<Mode, null>, prefill = "") => {
    setError(null);
    setId(prefill);
    setMode(m);
    setLoaded(false);
    void refresh();
  };
  const load = (item: WorkflowListItem) => {
    if (!discard()) return;
    getWorkflow(item.id).then((r) => { onLoad(r.document, r.id); setMode(null); }, setError);
  };
  const remove = (item: WorkflowListItem) => {
    if (!window.confirm(t("file.delete.confirm", { name: item.name }))) return;
    deleteWorkflow(item.id).then(() => { onDeleted(item.id); return refresh(); }, setError);
  };
  const save = () => {
    if (!FILE_ID_PATTERN.test(id)) return;
    if (id !== fileId && list.some((x) => x.id === id && x.source === "user") && !window.confirm(t("file.overwrite", { id }))) return;
    putWorkflow(id, wf).then((r) => { onSaved(r.id); setMode(null); }, setError);
  };

  const openSave = () => open("save", fileId ?? slugify(wf.name));
  useEffect(() => {
    if (!saveRef) return;
    saveRef.current = openSave;
    return () => { saveRef.current = null; };
  }); // every render: `openSave` closes over the current document and file

  const err = error instanceof Error ? error : null;
  return (
    <span className="filemenu" role="group" aria-label={t("file.menu")}>
      <button onClick={() => { if (discard()) onNew(); }}>{t("canvas.new")}</button>
      <button onClick={() => open("open")}>{t("file.open")}</button>
      <button onClick={openSave}>{t("file.save")}</button>
      <button onClick={() => open("save", slugify(wf.name))}>{t("file.saveas")}</button>
      {aiOn && <button onClick={() => { setDesc(""); setDraftName(""); setMode("draft"); }}>{t("ai.draft")}</button>}
      <span className="muted docname" role="status">{wf.name || t("file.untitled")}{dirty && <strong title={t("file.dirty")}> ● {t("file.dirty")}</strong>}</span>

      <Modal open={mode === "open"} title={t("file.open")} onCancel={() => setMode(null)}>
        {err && <p role="alert" className="error">{err.message}</p>}
        <Library items={list} onPick={load} onRemove={remove} />
        <div className="actions"><button onClick={() => setMode(null)}>{t("run.cancel")}</button></div>
      </Modal>

      <Modal open={mode === "draft"} title={t("ai.draft")} onCancel={() => setMode(null)}>
        <div className="field">
          <label htmlFor="ai-desc">{t("ai.draft.desc")}</label>
          <textarea id="ai-desc" rows={5} value={desc} data-autofocus onChange={(e) => setDesc(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="ai-name">{t("ai.draft.name")}</label>
          <input id="ai-name" value={draftName} onChange={(e) => setDraftName(e.target.value)} aria-invalid={draftName !== "" && !FILE_ID_PATTERN.test(draftName)} />
        </div>
        <div className="actions">
          <button onClick={() => setMode(null)}>{t("run.cancel")}</button>
          <button className="btn--primary" disabled={desc.trim() === "" || (draftName !== "" && !FILE_ID_PATTERN.test(draftName))} onClick={() => { setAsking(true); setMode(null); }}>{t("ai.next")}</button>
        </div>
      </Modal>
      {asking && (
        <AiDialog task="draft-workflow" title={t("ai.draft")} onClose={() => setAsking(false)}
          build={() => (draftName === "" ? { description: desc } : { description: desc, name: draftName })}
          onApplied={(r) => {
            const p = parseRaw(r.raw);
            if (p.ok && discard()) onDraft(p.doc as unknown as Workflow); // the server validated the proposal; the editor re-validates on load
          }} />
      )}

      <Modal open={mode === "save"} title={t("file.save")} onCancel={() => setMode(null)}>
        <div className="field">
          <label htmlFor="file-id">{t("file.id")}</label>
          <input id="file-id" value={id} data-autofocus onChange={(e) => setId(e.target.value)} aria-invalid={!FILE_ID_PATTERN.test(id)} />
          <small className="muted">{t("file.id.help")}</small>
        </div>
        {error instanceof ApiError && error.errors.length > 0 ? (
          <div role="alert" className="error"><p>{error.message}</p><ul>{error.errors.map((e, i) => <li key={i}><code>{e.path}</code> {e.message}</li>)}</ul></div>
        ) : err && <p role="alert" className="error">{err.message}</p>}
        <div className="actions">
          <button onClick={() => setMode(null)}>{t("run.cancel")}</button>
          <button className="btn--primary" onClick={save} disabled={!loaded || !FILE_ID_PATTERN.test(id)}>{t("file.save")}</button>
        </div>
      </Modal>
    </span>
  );
}
