// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure form <-> raw text logic of the module editor. The raw string is the source of truth;
// form edits patch the parsed document and re-serialize it (comments are lost, the editor says so).
import YAML from "yaml";
import { t } from "../i18n";

export type Doc = Record<string, unknown>;
export type RowList = "options" | "inputs";

export function parseRaw(raw: string): { ok: true; doc: Doc } | { ok: false; error: string } {
  try {
    const doc: unknown = YAML.parse(raw);
    if (doc && typeof doc === "object" && !Array.isArray(doc)) return { ok: true, doc: doc as Doc }; // checked above: a mapping
    return { ok: false, error: t("mod.nomapping") };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

/** Strings are always double-quoted: the backend may read `yes`, `2020-01-01` or `1e3` as bool/date/number otherwise. */
export const toRaw = (doc: Doc): string => YAML.stringify(doc, { defaultStringType: "QUOTE_DOUBLE", defaultKeyType: "PLAIN" });

/** Set a top-level key; empty string/undefined removes it. All other keys (examples, i18n, ...) stay untouched. */
export function setField(doc: Doc, key: string, value: unknown): Doc {
  const { [key]: _old, ...rest } = doc;
  return value === "" || value === undefined || value === null ? rest : { ...doc, [key]: value };
}

const isDoc = (v: unknown): v is Doc => !!v && typeof v === "object" && !Array.isArray(v);
const entries = (doc: Doc, list: RowList): unknown[] => (Array.isArray(doc[list]) ? (doc[list] as unknown[]) : []);

/** Rows that are mappings, with their index in the document; `bad` counts the others (shown as a hint, never edited). */
export function validRows(doc: Doc, list: RowList): { rows: { row: Doc; index: number }[]; bad: number } {
  const all = entries(doc, list);
  const rows = all.flatMap((row, index) => (isDoc(row) ? [{ row, index }] : []));
  return { rows, bad: all.length - rows.length };
}

/** Set a field of one option/input row; unknown row fields stay untouched. */
export function setRowField(doc: Doc, list: RowList, index: number, key: string, value: unknown): Doc {
  const next = entries(doc, list).map((r, i) => (i === index && isDoc(r) ? setField(r, key, value) : r));
  return { ...doc, [list]: next };
}

export const flagsToText = (v: unknown): string => (Array.isArray(v) ? v.join(", ") : "");
export const textToFlags = (s: string): string[] => s.split(/[\s,]+/).filter(Boolean);

export function exampleTitles(doc: Doc): string[] {
  const ex = doc.examples;
  return Array.isArray(ex) ? ex.map((e) => String((e as Doc | null)?.title ?? "")) : [];
}

export const str = (v: unknown): string => (typeof v === "string" ? v : "");
