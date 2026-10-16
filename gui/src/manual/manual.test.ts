// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { shouldOpenHelp } from "../Settings";
import { parseLink, searchChapters, slug, type ManualChapter } from "./manualData";

const ch = (id: string, title: string, text: string, headings: string[] = []): ManualChapter => ({
  id, title, html: "", text, headings: headings.map((h) => ({ id: slug(h), text: h, level: 2 as const })),
});
const chapters = [ch("start", "Erste Schritte", "Ein Workflow besteht aus Schritten.", ["Übersicht"]), ch("module", "Module", "Beschreibung der Werkzeuge.")];

test("slug transliterates and is stable", () => {
  expect(slug("Über Größe & Maß!")).toBe("ueber-groesse-mass");
  expect(slug("  Schritt 1: Start ")).toBe("schritt-1-start");
});

test("search is case-insensitive over title, headings and text", () => {
  expect(searchChapters(chapters, "  ")).toBeNull();
  expect(searchChapters(chapters, "WORKFLOW")?.map((h) => h.chapter.id)).toEqual(["start"]);
  expect(searchChapters(chapters, "module")?.map((h) => h.chapter.id)).toEqual(["module"]);
  expect(searchChapters(chapters, "übersicht")?.[0]?.headings.map((h) => h.id)).toEqual(["uebersicht"]);
  expect(searchChapters(chapters, "werkzeuge")?.[0]?.snippet).toContain("Werkzeuge");
  expect(searchChapters(chapters, "nichts")).toEqual([]);
});

test("links resolve to chapter and heading", () => {
  expect(parseLink("#module", chapters, "start")).toEqual({ chapter: "module" });
  expect(parseLink("#module/x", chapters, "start")).toEqual({ chapter: "module", heading: "x" });
  expect(parseLink("#uebersicht", chapters, "start")).toEqual({ chapter: "start", heading: "uebersicht" });
  expect(parseLink("https://x", chapters, "start")).toBeNull();
});

test("help opens on first start only when enabled", () => {
  expect(shouldOpenHelp(false, true)).toBe(true);
  expect(shouldOpenHelp(false, false)).toBe(false);
  expect(shouldOpenHelp(true, true)).toBe(false);
});
