// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { listTools } from "../api";
import { t } from "../i18n";
import type { ToolSummary } from "../types/api";
import { groupTools, label, OTHER } from "./groupTools";

const FAV_KEY = "wts.favorites";

function loadFavorites(): string[] {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(FAV_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function CatalogPanel({ selected, onSelect, onLoaded }: { selected: string | null; onSelect: (name: string) => void; onLoaded?: (tools: ToolSummary[]) => void }) {
  const [query, setQuery] = useState("");
  const [tools, setTools] = useState<ToolSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<string[]>(loadFavorites);

  useEffect(() => {
    let stale = false;
    const timer = setTimeout(() => {
      listTools(query.trim())
        .then((list) => { if (!stale) { setTools(list); setError(null); onLoaded?.(list); } })
        .catch((e: unknown) => { if (!stale) setError(e instanceof Error ? e.message : String(e)); });
    }, 150);
    return () => { stale = true; clearTimeout(timer); };
  }, [query]); // eslint-disable-line -- onLoaded is a stable setter wrapper

  const groups = useMemo(() => {
    const all = groupTools(tools ?? [], query);
    const favs = all.flatMap((g) => g.tools).filter((x) => favorites.includes(x.name));
    const rest = all
      .map((g) => ({ ...g, tools: g.tools.filter((x) => !favorites.includes(x.name)) }))
      .filter((g) => g.tools.length > 0);
    return favs.length ? [{ category: "★", tools: favs }, ...rest] : rest;
  }, [tools, query, favorites]);

  const toggle = (name: string) => {
    const next = favorites.includes(name) ? favorites.filter((n) => n !== name) : [...favorites, name];
    setFavorites(next);
    localStorage.setItem(FAV_KEY, JSON.stringify(next));
  };

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const items = [...e.currentTarget.querySelectorAll<HTMLElement>("button.tool")];
    const i = items.indexOf(document.activeElement as HTMLElement); // activeElement is an Element; only compared by identity
    const next = items[e.key === "ArrowDown" ? i + 1 : i - 1] ?? (i < 0 ? items[0] : undefined);
    if (next) { e.preventDefault(); next.focus(); }
  };

  const heading = (c: string) => (c === "★" ? t("catalog.favorites") : c === OTHER ? t("catalog.other") : c);

  return (
    <section className="panel" aria-labelledby="catalog-h">
      <h2 id="catalog-h">{t("catalog.title")}</h2>
      <input
        type="search"
        value={query}
        placeholder={t("catalog.search")}
        aria-label={t("catalog.search")}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); e.currentTarget.parentElement?.querySelector<HTMLElement>("button.tool")?.focus(); } }}
      />
      {error && <p role="alert" className="error">{t("error.network", { message: error })}</p>}
      {tools === null && !error && <p>{t("catalog.loading")}</p>}
      {tools !== null && groups.length === 0 && <p>{t("catalog.empty")}</p>}
      <div onKeyDown={onKeyDown}>
        {groups.map((g) => (
          <div key={g.category}>
            <h3>{heading(g.category)}</h3>
            <ul className="tools">
              {g.tools.map((tool) => (
                <li key={tool.name}>
                  <button className="tool" aria-current={selected === tool.name} onClick={() => onSelect(tool.name)}>
                    <span className="name">
                      {tool.safety && (
                        <>
                          <span className={`dot ${tool.safety}`} aria-hidden="true" />
                          <span className="sr-only">{t(`safety.${tool.safety}`)}: </span>
                        </>
                      )}
                      {label(tool)}
                    </span>
                    {tool.summary && <span className="summary">{tool.summary}</span>}
                  </button>
                  <button
                    className="star"
                    aria-pressed={favorites.includes(tool.name)}
                    aria-label={t(favorites.includes(tool.name) ? "catalog.fav.remove" : "catalog.fav.add", { name: label(tool) })}
                    onClick={() => toggle(tool.name)}
                  >
                    {favorites.includes(tool.name) ? "★" : "☆"}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
