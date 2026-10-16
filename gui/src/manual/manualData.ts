// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure helpers for the manual; the chapters themselves come from the build-time module `virtual:manual`.

export interface ManualHeading { id: string; text: string; level: 2 | 3 }
export interface ManualChapter { id: string; title: string; html: string; text: string; headings: ManualHeading[] }

/** Stable anchor id: lower case, umlauts transliterated, everything else non-alphanumeric becomes "-". */
export const slug = (text: string): string =>
  text.toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

export interface ManualHit { chapter: ManualChapter; snippet: string; headings: ManualHeading[] }

const SNIPPET = 60;

/** Case-insensitive substring search over chapter title, headings and text. Empty query: no filtering (null). */
export function searchChapters(chapters: readonly ManualChapter[], query: string): ManualHit[] | null {
  const q = query.trim().toLowerCase();
  if (!q) return null;
  const hits: ManualHit[] = [];
  for (const chapter of chapters) {
    const headings = chapter.headings.filter((h) => h.text.toLowerCase().includes(q));
    const at = chapter.text.toLowerCase().indexOf(q);
    if (at < 0 && headings.length === 0 && !chapter.title.toLowerCase().includes(q)) continue;
    const from = Math.max(0, at - SNIPPET);
    const snippet = at < 0 ? "" : `${from > 0 ? "…" : ""}${chapter.text.slice(from, at + q.length + SNIPPET).trim()}…`;
    hits.push({ chapter, snippet, headings });
  }
  return hits;
}

/** `#chapter` or `#chapter/heading` (or `#heading` inside the current chapter) → target, else null. */
export function parseLink(href: string, chapters: readonly ManualChapter[], current: string): { chapter: string; heading?: string } | null {
  if (!href.startsWith("#")) return null;
  const [a = "", b] = href.slice(1).split("/");
  if (chapters.some((c) => c.id === a)) return b ? { chapter: a, heading: b } : { chapter: a };
  return a && b === undefined ? { chapter: current, heading: a } : null;
}
