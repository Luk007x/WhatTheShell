// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";
import { errMsg, getTemplates, type TemplateEntry } from "../api";
import { t } from "../i18n";
import type { Workflow } from "../types/workflow";

/** Templates of the modules of `tool`; "Insert" hands the template document to the caller. */
export function Templates({ tool, onInsert }: { tool: string; onInsert: (doc: Workflow) => void }) {
  const [list, setList] = useState<TemplateEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let stale = false;
    setError(null);
    setList([]);
    getTemplates(tool).then((l) => { if (!stale) setList(l); }, (e: unknown) => { if (!stale) { setList([]); setError(errMsg(e)); } });
    return () => { stale = true; };
  }, [tool]);
  if (list.length === 0 && !error) return null;
  return (
    <section aria-label={t("tpl.title")}>
      <h4>{t("tpl.title")}</h4>
      {error && <p role="alert" className="error">{error}</p>}
      <ul className="tpl">
        {list.map((x, i) => (
          <li key={i}>
            {x.title}{" "}
            {x.workflow.document
              ? <button aria-label={t("tpl.insert.for", { title: x.title })} onClick={() => x.workflow.document && onInsert(x.workflow.document)}>{t("tpl.insert")}</button>
              : <span className="error">{x.error ?? ""}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
