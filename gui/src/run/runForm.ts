// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure logic of the run form: values per workflow variable, checks, and the string overrides the API expects.
import { allSteps, isTerminal, type Step } from "../model/ops";
import type { VariableSpec, WorkflowListItem } from "../types/api";
import type { Workflow } from "../types/workflow";

/** Form state: checkboxes hold booleans, every other field its text. */
export type FormValues = Record<string, string | boolean>;
export type FieldError = "required" | "int" | "float" | "choice" | "min" | "max" | "pattern";
type Entry = Pick<WorkflowListItem, "variables">;

const INT = /^[+-]?\d+$/;
const FLOAT = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;
/** Types whose text is trimmed before sending; string and secret values go out as typed. */
const TRIMMED = new Set(["int", "float", "path"]);

/** The regex of a string variable, if any. */
export const patternOf = (v: VariableSpec): string | undefined => v.pattern || undefined;

/** Full match like the backend (`fullmatch`) and the HTML `pattern` attribute; an invalid regex is left to the backend. */
export function matchesPattern(pattern: string, text: string): boolean {
  try {
    return new RegExp(`^(?:${pattern})$`, "v").test(text);
  } catch {
    return true;
  }
}

/** Stored values (if they fit the variable type) win over defaults; secrets never come from storage. */
export function initialValues(entry: Entry, stored: unknown): FormValues {
  const saved: Record<string, unknown> = stored !== null && typeof stored === "object" ? { ...stored } : {};
  return Object.fromEntries(Object.entries(entry.variables).map(([name, v]) => {
    const s = v.type === "secret" ? undefined : saved[name];
    if (v.type === "bool") return [name, typeof s === "boolean" ? s : v.default === true];
    return [name, typeof s === "string" ? s : v.default === undefined || v.default === null ? "" : String(v.default)];
  }));
}

/** Errors per variable name; an empty object means the form can be sent. */
export function validate(entry: Entry, values: FormValues): Record<string, FieldError> {
  const errors: Record<string, FieldError> = {};
  for (const [name, v] of Object.entries(entry.variables)) {
    const raw = values[name];
    if (typeof raw !== "string") continue; // checkboxes are always valid
    const text = TRIMMED.has(v.type ?? "string") ? raw.trim() : raw;
    if (text === "") {
      if (v.required) errors[name] = "required";
      continue;
    }
    if (v.type === "int" && !INT.test(text)) errors[name] = "int";
    else if (v.type === "float" && !FLOAT.test(text)) errors[name] = "float";
    else if (v.type === "enum" && v.choices && v.choices.length > 0 && !v.choices.includes(text)) errors[name] = "choice";
    else if ((v.type === "int" || v.type === "float") && v.min != null && Number(text) < v.min) errors[name] = "min";
    else if ((v.type === "int" || v.type === "float") && v.max != null && Number(text) > v.max) errors[name] = "max";
    else if (v.type === "string" && patternOf(v) !== undefined && !matchesPattern(patternOf(v) ?? "", text)) errors[name] = "pattern";
  }
  return errors;
}

/** `variables` of a run request: booleans as "true"/"false", empty fields left out (the default applies). */
export function toOverrides(entry: Entry, values: FormValues): Record<string, string> {
  return Object.fromEntries(Object.entries(values).flatMap(([k, v]) => {
    if (!(k in entry.variables)) return []; // not part of the form (e.g. asked during the run)
    if (typeof v === "boolean") return [[k, v ? "true" : "false"]];
    const text = TRIMMED.has(entry.variables[k]?.type ?? "string") ? v.trim() : v;
    return text === "" ? [] : [[k, text]];
  }));
}

/** `values` of an ask answer: every field is sent, empty text as "" (unlike run overrides, there is no default to fall back on). */
export const askValues = (entry: Entry, values: FormValues): Record<string, string> =>
  ({ ...Object.fromEntries(Object.keys(entry.variables).map((k) => [k, ""])), ...toOverrides(entry, values) });

/** What may be remembered in localStorage: declared, non-secret variables only. */
export function storable(entry: Entry, values: FormValues): FormValues {
  return Object.fromEntries(Object.entries(entry.variables).flatMap(([k, v]) => {
    const value = values[k];
    return v.type === "secret" || value === undefined ? [] : [[k, value]];
  }));
}

/** Variables an `ask` step collects during the run (fields, button_variable; any depth): not asked in the start form. */
export function askedVariables(wf: Pick<Workflow, "steps">): Set<string> {
  const out = new Set<string>();
  for (const s of allSteps(wf.steps)) {
    if (s.kind !== "ask") continue;
    for (const f of s.fields ?? []) out.add(f);
    if (s.button_variable) out.add(s.button_variable);
  }
  return out;
}

/** The entry without the asked variables, for form, required check and overrides. */
export const withoutAsked = (entry: Entry, asked: ReadonlySet<string>): Entry =>
  ({ variables: Object.fromEntries(Object.entries(entry.variables).filter(([k]) => !asked.has(k))) });

/** Does the workflow contain a terminal step (at any depth)? Only then the transcript option is offered. */
export const hasTerminal = (steps: Step[]): boolean => allSteps(steps).some(isTerminal);
