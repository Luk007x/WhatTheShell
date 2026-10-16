// SPDX-License-Identifier: AGPL-3.0-or-later
// Searchable workflow list grouped by source; used by the run view and the editor's "Öffnen" dialog.
import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { acceptWorkflow, ApiError, importWorkflow } from "../api";
import { t } from "../i18n";
import { Icon } from "../icons";
import { Modal } from "../Modal";
import { Problem } from "../run/RunPanel";
import type { WorkflowListItem, WorkflowSource } from "../types/api";
import { FILTER_KEY, FILTERS, IMPORT_SUFFIX, loadFilter, matchesFilter, MAX_IMPORT_BYTES, needsAccept, proposeImportName, type LibFilter } from "./libraryImport";

const SOURCES: WorkflowSource[] = ["bundled", "user", "project"];

/** "Prüfen und übernehmen": the server stamps the file; errors (422 invalid) stay visible via `onError`. */
export function AcceptButton({ id, onDone, onError }: { id: string; onDone: () => void; onError: (e: unknown) => void }) {
  return <button className="btn--sm" onClick={() => { acceptWorkflow(id).then(onDone, onError); }}>{t("lib.accept")}</button>;
}

export function Library({ items, selected = null, onPick, onRemove, onChanged }: {
  items: WorkflowListItem[]; selected?: string | null; onPick: (item: WorkflowListItem) => void; onRemove?: (item: WorkflowListItem) => void;
  /** After accept or import: reload the list; `item` is the imported entry. */
  onChanged: (item?: WorkflowListItem) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<LibFilter>(loadFilter);
  const [problem, setProblem] = useState<unknown>(null);
  const [pending, setPending] = useState<{ name: string; content: string } | null>(null); // import dialog
  const [importError, setImportError] = useState<unknown>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => { // a file dropped outside the list must not navigate the browser away (token loss)
    const stop = (e: globalThis.DragEvent) => { if (e.dataTransfer?.types.includes("Files")) e.preventDefault(); };
    window.addEventListener("dragover", stop);
    window.addEventListener("drop", stop);
    return () => { window.removeEventListener("dragover", stop); window.removeEventListener("drop", stop); };
  }, []);
  const hasProject = items.some((x) => x.source === "project");
  const active: LibFilter = filter === "project" && !hasProject ? "all" : filter;
  const pickFilter = (f: LibFilter) => {
    setFilter(f);
    try { localStorage.setItem(FILTER_KEY, f); } catch { /* storage unavailable: filter lasts for this session */ }
  };
  const readFile = (file: File | undefined) => {
    if (!file) return;
    setProblem(null);
    if (file.size > MAX_IMPORT_BYTES) { setProblem(new Error(t("lib.import.big"))); return; }
    file.text().then((content) => { setImportError(null); setPending({ name: proposeImportName(file.name), content }); }, setProblem);
  };
  const submit = (overwrite: boolean) => {
    if (!pending) return;
    importWorkflow(pending.name, pending.content, overwrite).then((item) => { setPending(null); onChanged(item); }, setImportError);
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDragging(false); readFile(e.dataTransfer.files[0]); };
  const ie = importError instanceof ApiError ? importError : null;
  const uid = useId();
  const needle = query.trim().toLowerCase();
  const shown = items.filter((x) => matchesFilter(active, x.source) && (needle === "" || [x.id, x.name, x.description ?? ""].some((s) => s.toLowerCase().includes(needle))));
  const source = (s: WorkflowSource) => t(`file.source.${s}`);
  return (
    <>
      <div className="lib-tools">
        <div role="group" aria-label={t("lib.filter")} className="segmented">
          {FILTERS.filter((f) => f !== "project" || hasProject).map((f) => (
            <button key={f} aria-pressed={active === f} onClick={() => pickFilter(f)}>{t(`lib.filter.${f}`)}</button>
          ))}
        </div>
        <button className="btn--sm" onClick={() => fileInput.current?.click()}>{t("lib.import")}</button>
        <input ref={fileInput} type="file" accept=".yaml,.yml" hidden aria-label={t("lib.import")} onChange={(e) => { readFile(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
      {problem !== null && <Problem error={problem} />}
      <div className="search">
        <Icon name="search" />
        <input type="search" aria-label={t("lib.search")} placeholder={t("lib.search")} value={query} data-autofocus onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className={dragging ? "panel__body catalog lib lib--drop" : "panel__body catalog lib"} title={t("lib.import.drop")}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={(e) => { if (!(e.relatedTarget instanceof Node && e.currentTarget.contains(e.relatedTarget))) setDragging(false); }} onDrop={onDrop}>
        {shown.length === 0 && <p className="muted">{t("file.none")}</p>}
        {SOURCES.map((src) => {
          const group = shown.filter((x) => x.source === src);
          if (group.length === 0) return null;
          return (
            <div key={src}>
              <h3 id={`${uid}-${src}`}>{source(src)}</h3>
              <ul className="tools" aria-labelledby={`${uid}-${src}`}>
                {group.map((x) => (
                  <li key={x.id}>
                    <button className="tool" aria-current={selected === x.id} disabled={x.error !== null || x.integrity === "invalid"} onClick={() => onPick(x)}>
                      <span className="name">{x.name}</span>
                      <span className="summary">{x.id} · {t("lib.steps", { n: x.steps })}{x.description ? ` · ${x.description}` : ""}</span>
                      <span className="lib-meta">
                        <span className="badge">{source(x.source)}</span>
                        {needsAccept(x) && <span className="badge badge--caution">{t(`lib.int.${x.integrity}`)}</span>}
                        {x.integrity === "invalid" && <span className="badge badge--dangerous" title={x.error ?? undefined}>{t("lib.int.invalid")}</span>}
                        {x.shadows.length > 0 && <span className="muted">{t("lib.shadows", { list: x.shadows.map(source).join(", ") })}</span>}
                        {!x.writable && <span className="muted">{t("lib.readonly")}</span>}
                      </span>
                      {x.error !== null && <span className="error lib-error">{x.error}</span>}
                    </button>
                    {needsAccept(x) && <AcceptButton id={x.id} onDone={() => { setProblem(null); onChanged(); }} onError={setProblem} />}
                    {onRemove && x.source === "user" && (
                      <button className="btn--danger btn--sm" aria-label={`${t("file.delete")} ${x.name}`} onClick={() => onRemove(x)}>{t("file.delete")}</button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
      <Modal open={pending !== null} title={t("lib.import")} onCancel={() => setPending(null)}>
        <div className="field">
          <label htmlFor="lib-import-name">{t("lib.import.name")}</label>
          <input id="lib-import-name" value={pending?.name ?? ""} data-autofocus aria-invalid={!(pending?.name ?? "").endsWith(IMPORT_SUFFIX)}
            onChange={(e) => { setImportError(null); setPending(pending && { ...pending, name: e.target.value }); }} />
          <small className="muted">{t("lib.import.help")}</small>
        </div>
        {ie?.error === "exists" && <p role="alert" className="error">{t("lib.import.exists", { name: pending?.name ?? "" })}</p>}
        {ie?.error === "shadowed" && <p role="alert" className="error">{t("lib.import.shadowed")}</p>}
        {importError !== null && ie?.error !== "exists" && ie?.error !== "shadowed" && <Problem error={importError} />}
        <div className="actions">
          <button onClick={() => setPending(null)}>{t("run.cancel")}</button>
          {ie?.error === "exists"
            ? <button className="btn--danger" onClick={() => submit(true)}>{t("lib.import.overwrite")}</button>
            : <button className="btn--primary" disabled={!(pending?.name ?? "").endsWith(IMPORT_SUFFIX)} onClick={() => submit(false)}>{t("lib.import")}</button>}
        </div>
      </Modal>
    </>
  );
}
