// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { listTools } from "../api";
import { HelpButton } from "../Help";
import { t } from "../i18n";
import type { ToolSummary } from "../types/api";
import { Icon } from "../icons";
import { categoryClass, groupTools, label, OTHER } from "./groupTools";
import { MIME_TOOL } from "../model/blocks";

const FAV_KEY = "wts.favorites";

function loadFavorites(): string[] {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(FAV_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function CatalogPanel({ selected, onSelect, onLoaded, onAdd, reloadKey = 0 }: { selected: string | null; onSelect: (name: string) => void; /** Ctrl/Cmd+Enter on an entry: append the tool to the workflow. */ onAdd?: (name: string) => void; onLoaded?: (tools: ToolSummary[]) => void; reloadKey?: number }) {
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
  }, [query, reloadKey]); // eslint-disable-line -- onLoaded is a stable setter wrapper

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
    try {
      localStorage.setItem(FAV_KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable: favorites last for this session only */
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && e.target instanceof HTMLElement && e.target.matches("button.tool")) { e.preventDefault(); if (!e.repeat) onAdd?.(e.target.dataset.tool ?? ""); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const items = [...e.currentTarget.querySelectorAll<HTMLElement>("button.tool")];
    const i = items.indexOf(document.activeElement as HTMLElement); // activeElement is an Element; only compared by identity
    const next = items[e.key === "ArrowDown" ? i + 1 : i - 1] ?? (i < 0 ? items[0] : undefined);
    if (next) { e.preventDefault(); next.focus(); }
  };

  const heading = (c: string) => (c === "★" ? t("catalog.favorites") : c === OTHER ? t("catalog.other") : c);

  return (
    <section className="panel catalog" aria-labelledby="catalog-h">
      <div className="panel__header"><h2 id="catalog-h">{t("catalog.title")}</h2><HelpButton section="run" topic={t("catalog.title")} /></div>
      <div className="search">
      <Icon name="search" />
      <input
        type="search"
        value={query}
        placeholder={t("catalog.search")}
        aria-label={t("catalog.search")}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); e.currentTarget.closest("section")?.querySelector<HTMLElement>("button.tool")?.focus(); } }}
      />
      </div>
      <div className="panel__body">
      {error && <p role="alert" className="error">{t("error.network", { message: error })}</p>}
      {tools === null && !error && <p>{t("catalog.loading")}</p>}
      {tools !== null && groups.length === 0 && <p>{t("catalog.empty")}</p>}
      <div onKeyDown={onKeyDown}>
        {groups.map((g) => (
          <div key={g.category}>
            <h3><span className={`cat-chip ${g.category === "★" ? "cat-fav" : categoryClass(g.category)}`} aria-hidden="true" />{heading(g.category)}</h3>
            <ul className="tools">
              {g.tools.map((tool) => (
                <li key={tool.name}>
                  <button className="tool" data-tool={tool.name} aria-current={selected === tool.name} onClick={() => onSelect(tool.name)}
                    draggable onDragStart={(e) => { e.dataTransfer.setData(MIME_TOOL, tool.name); e.dataTransfer.effectAllowed = "copy"; }}>
                    <span className="name">
                      {tool.safety && (
                        <>
                          <span className={`dot ${tool.safety}`} aria-hidden="true" />
                          <span className="sr-only">{t(`safety.${tool.safety}`)}: </span>
                        </>
                      )}
                      {label(tool)}
                      {tool.interactive && <span className="badge"><Icon name="terminal" />{t("kind.terminal")}<span className="sr-only">: {t("catalog.interactive")}</span></span>}
                    </span>
                    {tool.summary && <span className="summary">{tool.summary}</span>}
                  </button>
                  <button
                    className="star"
                    aria-pressed={favorites.includes(tool.name)}
                    aria-label={t(favorites.includes(tool.name) ? "catalog.fav.remove" : "catalog.fav.add", { name: label(tool) })}
                    onClick={() => toggle(tool.name)}
                  >
                    <Icon name="star" filled={favorites.includes(tool.name)} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      </div>
    </section>
  );
}
