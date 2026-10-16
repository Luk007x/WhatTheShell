// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { manual } from "virtual:manual";
import { getLang, t } from "../i18n";
import { parseLink, searchChapters } from "./manualData";

/** Full-screen manual below the app header. `initial` is a chapter id (unknown or empty: first chapter). */
export function ManualView({ initial }: { initial: string }) {
  const lang = getLang();
  const fallback = manual[lang].length === 0 && manual[lang === "de" ? "en" : "de"].length > 0; // chosen language has no chapters yet
  const chapters = manual[fallback ? (lang === "de" ? "en" : "de") : lang];
  const [id, setId] = useState(() => (chapters.some((c) => c.id === initial) ? initial : (chapters[0]?.id ?? "")));
  const [query, setQuery] = useState("");
  const target = useRef<string | undefined>(undefined); // heading to scroll to after the next chapter render
  const article = useRef<HTMLElement>(null);
  const index = chapters.findIndex((c) => c.id === id);
  const chapter = chapters[index];
  const hits = useMemo(() => searchChapters(chapters, query), [chapters, query]);

  const toHeading = (heading: string) => { const el = document.getElementById(heading); el?.scrollIntoView({ block: "start" }); el?.focus({ preventScroll: true }); };
  const go = (chapterId: string, heading?: string) => {
    if (chapterId === id) { setQuery(""); if (heading) toHeading(heading); return; } // same chapter: the scroll effect would not run
    target.current = heading; setId(chapterId); setQuery("");
  };

  useEffect(() => { // focus the chapter h1 (or scroll to the wanted heading) when the chapter changes
    const el = target.current ? document.getElementById(target.current) : null;
    if (el) toHeading(target.current ?? "");
    else { const h1 = article.current?.querySelector<HTMLElement>("h1"); h1?.scrollIntoView({ block: "start" }); h1?.focus({ preventScroll: true }); }
    target.current = undefined;
  }, [id]);

  const onLink = (e: MouseEvent) => {
    const a = e.target instanceof Element ? e.target.closest("a") : null;
    const to = a && parseLink(a.getAttribute("href") ?? "", chapters, id);
    if (!to) return;
    e.preventDefault();
    go(to.chapter, to.heading);
  };

  if (!chapter) return <main id="main" tabIndex={-1} className="manual manual--empty"><p>{t("manual.empty")}</p></main>;
  const prev = chapters[index - 1];
  const next = chapters[index + 1];
  return (
    <main id="main" tabIndex={-1} className="manual">
      <nav className="manual__toc" aria-label={t("manual.toc")}>
        <input type="search" aria-label={t("manual.search")} placeholder={t("manual.search")} value={query} onChange={(e) => setQuery(e.target.value)} />
        {hits ? (
          hits.length === 0 ? <p className="muted" role="status">{t("manual.nohits")}</p> : (
            <ul role="status">
              {hits.map((h) => (
                <li key={h.chapter.id}>
                  <button onClick={() => go(h.chapter.id)}>{h.chapter.title}</button>
                  {h.snippet && <p className="muted">{h.snippet}</p>}
                  <ul>{h.headings.map((s) => <li key={s.id}><button onClick={() => go(h.chapter.id, s.id)}>{s.text}</button></li>)}</ul>
                </li>
              ))}
            </ul>
          )
        ) : (
          <ul>
            {chapters.map((c) => (
              <li key={c.id}>
                <button aria-current={c.id === id ? "page" : undefined} onClick={() => go(c.id)}>{c.title}</button>
                {c.id === id && <ul>{c.headings.map((h) => <li key={h.id} className={h.level === 3 ? "lvl3" : undefined}><button onClick={() => go(c.id, h.id)}>{h.text}</button></li>)}</ul>}
              </li>
            ))}
          </ul>
        )}
      </nav>
      <article className="manual__body" ref={article} onClick={onLink}>
        {fallback && <p className="muted" role="note">{t("manual.german")}</p>}
        {/* build-time HTML of our own docs/manual/*.md, not user input */}
        <div dangerouslySetInnerHTML={{ __html: chapter.html }} />
        <div className="manual__pager">
          {prev ? <button onClick={() => go(prev.id)}>← {prev.title}</button> : <span />}
          {next && <button onClick={() => go(next.id)}>{next.title} →</button>}
        </div>
      </article>
    </main>
  );
}
