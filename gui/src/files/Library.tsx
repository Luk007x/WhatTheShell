// SPDX-License-Identifier: AGPL-3.0-or-later
// Searchable workflow list grouped by source; used by the run view and the editor's "Öffnen" dialog.
import { useId, useState } from "react";
import { t } from "../i18n";
import { Icon } from "../icons";
import type { WorkflowListItem, WorkflowSource } from "../types/api";

const SOURCES: WorkflowSource[] = ["bundled", "user", "project"];

export function Library({ items, selected = null, onPick, onRemove }: {
  items: WorkflowListItem[]; selected?: string | null; onPick: (item: WorkflowListItem) => void; onRemove?: (item: WorkflowListItem) => void;
}) {
  const [query, setQuery] = useState("");
  const uid = useId();
  const needle = query.trim().toLowerCase();
  const shown = items.filter((x) => needle === "" || [x.id, x.name, x.description ?? ""].some((s) => s.toLowerCase().includes(needle)));
  const source = (s: WorkflowSource) => t(`file.source.${s}`);
  return (
    <>
      <div className="search">
        <Icon name="search" />
        <input type="search" aria-label={t("lib.search")} placeholder={t("lib.search")} value={query} data-autofocus onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="panel__body catalog lib">
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
                    <button className="tool" aria-current={selected === x.id} disabled={x.error !== null} onClick={() => onPick(x)}>
                      <span className="name">{x.name}</span>
                      <span className="summary">{x.id} · {t("lib.steps", { n: x.steps })}{x.description ? ` · ${x.description}` : ""}</span>
                      <span className="lib-meta">
                        <span className="badge">{source(x.source)}</span>
                        {x.shadows.length > 0 && <span className="muted">{t("lib.shadows", { list: x.shadows.map(source).join(", ") })}</span>}
                        {!x.writable && <span className="muted">{t("lib.readonly")}</span>}
                      </span>
                      {x.error !== null && <span className="error lib-error">{x.error}</span>}
                    </button>
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
    </>
  );
}
