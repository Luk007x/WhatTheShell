// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure form logic for the step panel.
import type { InputSpec, OptionSpec } from "../types/api";

export type Spec = InputSpec | OptionSpec;
export type FieldKind = "checkbox" | "number" | "select" | "text" | "path" | "password" | "textarea" | "tuple";

/** Which control to render. A template string in a numeric field falls back to text (no client type check). */
export function fieldKind(spec: Spec, value?: unknown): FieldKind {
  if (spec.type === "bool") return "checkbox";
  if (spec.type === "secret") return "password";
  if (spec.multiple) return "textarea";
  if ("nargs" in spec && (spec.nargs ?? 1) > 1) return "tuple";
  if (spec.type === "enum" || (spec.choices ?? []).length > 0) return "select";
  if (spec.type === "int" || spec.type === "float") return typeof value === "string" && value.includes("{{") ? "text" : "number";
  return spec.type === "path" ? "path" : "text";
}

export interface OptionGroups {
  groups: { name: string | null; options: OptionSpec[] }[];
  rare: OptionSpec[];
}

export function matchesQuery(o: OptionSpec, query: string): boolean {
  const q = query.trim().toLowerCase();
  return !q || [...(o.flags ?? []), o.label, o.help, o.id].some((s) => s?.toLowerCase().includes(q));
}

/** Group by `group` (unnamed last), `common` before the rest, `rare` split into one collapsed list. */
export function sortOptions(options: OptionSpec[], query = ""): OptionGroups {
  const hits = options.filter((o) => matchesQuery(o, query));
  const byGroup = new Map<string | null, OptionSpec[]>();
  for (const o of hits.filter((x) => x.importance !== "rare")) {
    const k = o.group ?? null;
    byGroup.set(k, [...(byGroup.get(k) ?? []), o]);
  }
  const rank = (o: OptionSpec) => (o.importance === "common" ? 0 : 1);
  const groups = [...byGroup.entries()]
    .sort(([a], [b]) => (a === null ? 1 : b === null ? -1 : 0)) // stable: named groups keep first-seen order
    .map(([name, list]) => ({ name, options: [...list].sort((a, b) => rank(a) - rank(b)) }));
  return { groups, rare: hits.filter((o) => o.importance === "rare") };
}

export type RawValue = string | boolean | string[];

/** Value shown in the control for the stored arg. */
export function rawFromArg(spec: Spec, value: unknown): RawValue {
  const kind = fieldKind(spec, value);
  if (kind === "checkbox") return value === true;
  if (kind === "textarea") return Array.isArray(value) ? value.map(String) : value === undefined || value === null ? [] : [String(value)];
  if (kind === "tuple") return Array.isArray(value) ? value.map(String) : [];
  return value === undefined || value === null ? "" : String(value);
}

/** New args after the user edited the field of `spec`; empty values remove the key. */
export function argsFromForm(args: Record<string, unknown>, spec: Spec, raw: RawValue): Record<string, unknown> {
  const { [spec.id]: _old, ...rest } = args;
  const kind = fieldKind(spec, raw);
  let value: unknown;
  if (kind === "checkbox") value = raw === true ? true : undefined;
  else if (Array.isArray(raw)) {
    const items = kind === "textarea" ? raw.filter((x) => x !== "") : raw;
    value = items.some((x) => x !== "") ? items : undefined;
  } else if (typeof raw === "string" && raw !== "") {
    value = kind === "number" && !Number.isNaN(Number(raw)) ? Number(raw) : raw;
  }
  return value === undefined ? rest : { ...rest, [spec.id]: value };
}

/** Textarea text (one value per line) to list. */
export const linesOf = (text: string): string[] => text.split("\n");

/** First sentence of a help text for the short line under a field. */
export function firstSentence(help: string | null | undefined): string {
  if (!help) return "";
  const m = /^(.+?[.!?])(\s|$)/s.exec(help.trim());
  return (m?.[1] ?? help.trim()).replace(/\s+/g, " ");
}

export const OPERATORS = [
  ["eq", "text"], ["ne", "text"], ["contains", "text"], ["regex", "text"], ["is_empty", "bool"],
  ["line_count_gt", "number"], ["line_count_eq", "number"], ["number_gt", "number"], ["number_lt", "number"],
  ["number_eq", "number"], ["json_path", "text"], ["file_exists", "bool"],
] as const;
export type OperatorName = (typeof OPERATORS)[number][0];

/** The single operator set on a condition, if any. */
export function conditionOperator(c: object): OperatorName | undefined {
  return OPERATORS.map(([k]) => k).find((k) => Reflect.get(c, k) != null);
}

/** Condition with exactly the operator `op` (value from `raw`), keeping `source`. */
export function conditionWith(c: { source: string }, op: OperatorName, raw: string | boolean): Record<string, unknown> {
  const kind = OPERATORS.find(([k]) => k === op)?.[1];
  const value = kind === "bool" ? raw === true || raw === "true" : kind === "number" ? (raw === "" ? 0 : Number(raw)) : String(raw);
  return { source: c.source, [op]: value };
}
