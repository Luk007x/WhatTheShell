// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { ApiError, deleteWorkflow, getWorkflow, listWorkflows, putWorkflow } from "../api";
import { t } from "../i18n";
import { FILE_ID_PATTERN, slugify } from "../model/files";
import { Modal } from "../Modal";
import type { WorkflowListItem } from "../types/api";
import type { Workflow } from "../types/workflow";

type Mode = null | "open" | "save";

export function FileMenu({ wf, fileId, dirty, onLoad, onSaved, onDeleted, onNew }: {
  wf: Workflow; fileId: string | null; dirty: boolean;
  onLoad: (doc: Workflow, id: string) => void; onSaved: (id: string) => void; onDeleted: (id: string) => void; onNew: () => void;
}) {
  const [mode, setMode] = useState<Mode>(null);
  const [list, setList] = useState<WorkflowListItem[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [id, setId] = useState("");
  const discard = () => !dirty || window.confirm(t("file.discard"));
  const refresh = () => listWorkflows().then(setList, setError);

  const open = (m: Exclude<Mode, null>, prefill = "") => {
    setError(null);
    setId(prefill);
    setMode(m);
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

  const err = error instanceof Error ? error : null;
  return (
    <span className="filemenu" role="group" aria-label={t("file.menu")}>
      <button onClick={() => { if (discard()) onNew(); }}>{t("canvas.new")}</button>
      <button onClick={() => open("open")}>{t("file.open")}</button>
      <button onClick={() => (fileId ? open("save", fileId) : open("save", slugify(wf.name)))}>{t("file.save")}</button>
      <button onClick={() => open("save", slugify(wf.name))}>{t("file.saveas")}</button>
      <span className="muted" role="status">{wf.name || t("file.untitled")}{dirty && <strong title={t("file.dirty")}> ● {t("file.dirty")}</strong>}</span>

      <Modal open={mode === "open"} title={t("file.open")} onCancel={() => setMode(null)}>
        {err && <p role="alert" className="error">{err.message}</p>}
        {list.length === 0 && <p>{t("file.none")}</p>}
        <ul className="filelist">
          {list.map((x) => (
            <li key={`${x.source}:${x.id}`}>
              <button onClick={() => load(x)}>{x.name} <small className="muted">{x.id} · {t(`file.source.${x.source}`)}</small></button>
              {x.source === "user" && <button aria-label={`${t("file.delete")} ${x.name}`} onClick={() => remove(x)}>{t("file.delete")}</button>}
            </li>
          ))}
        </ul>
        <div className="actions"><button autoFocus onClick={() => setMode(null)}>{t("run.cancel")}</button></div>
      </Modal>

      <Modal open={mode === "save"} title={t("file.save")} onCancel={() => setMode(null)}>
        <div className="field">
          <label htmlFor="file-id">{t("file.id")}</label>
          <input id="file-id" value={id} autoFocus onChange={(e) => setId(e.target.value)} aria-invalid={!FILE_ID_PATTERN.test(id)} />
          <small className="muted">{t("file.id.help")}</small>
        </div>
        {error instanceof ApiError && error.errors.length > 0 ? (
          <div role="alert" className="error"><p>{error.message}</p><ul>{error.errors.map((e, i) => <li key={i}><code>{e.path}</code> {e.message}</li>)}</ul></div>
        ) : err && <p role="alert" className="error">{err.message}</p>}
        <div className="actions">
          <button onClick={() => setMode(null)}>{t("run.cancel")}</button>
          <button onClick={save} disabled={!FILE_ID_PATTERN.test(id)}>{t("file.save")}</button>
        </div>
      </Modal>
    </span>
  );
}
