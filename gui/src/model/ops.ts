// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure, immutable edit operations on the workflow document (F-33). The graph is derived, never edited.
import type { CommandStep, ForeachStep, IfStep, TerminalStep, Workflow } from "../types/workflow";

export type Step = Workflow["steps"][number];
export type Port = "then" | "else" | "body" | "fallback";
/** Sequence address: [] = root, otherwise pairs of step id and port, e.g. ["pruefe", "then", "x", "fallback"]. */
export type SeqPath = string[];
export interface OpResult {
  wf: Workflow;
  warnings: string[];
  /** id of a step the operation created, if any. */
  created?: string;
}

export const ID_PATTERN = /^[a-z][a-z0-9_]*$/;
const RESERVED = new Set(["var", "item"]);
const PORTS: readonly Port[] = ["then", "else", "body", "fallback"];

export const isPort = (s: string | undefined): s is Port => PORTS.includes(s as Port); // widening check only
export const isCommand = (s: Step): s is CommandStep => s.kind === undefined || s.kind === "command";
/** Interactive step: shares the command fields, but has no stdin and no recorded output. */
export const isTerminal = (s: Step): s is TerminalStep => s.kind === "terminal";
/** Steps that run a tool (command or terminal). */
export const isToolStep = (s: Step): s is CommandStep | TerminalStep => isCommand(s) || isTerminal(s);
const isIf = (s: Step): s is IfStep => s.kind === "if";
const isForeach = (s: Step): s is ForeachStep => s.kind === "foreach";

/** Ports a step type offers; `fallback` only when the command has fallback steps. */
export function portsOf(step: Step): Port[] {
  if (isIf(step)) return ["then", "else"];
  if (isForeach(step)) return ["body"];
  return isToolStep(step) && step.on_error?.steps ? ["fallback"] : [];
}

export function childSeq(step: Step, port: Port): Step[] | undefined {
  if (isIf(step)) return port === "then" ? step.then : port === "else" ? (step.else ?? undefined) : undefined;
  if (isForeach(step)) return port === "body" ? step.body : undefined;
  return isToolStep(step) && port === "fallback" ? (step.on_error?.steps ?? undefined) : undefined;
}

function setChild(step: Step, port: Port, seq: Step[]): Step {
  if (isIf(step)) {
    if (port === "then") return { ...step, then: seq };
    if (port !== "else") return step;
    const { else: _drop, ...rest } = step;
    return seq.length === 0 ? rest : { ...rest, else: seq };
  }
  if (isForeach(step)) return port === "body" ? { ...step, body: seq } : step;
  if (isToolStep(step) && port === "fallback") {
    const { on_error: _oe, ...rest } = step;
    // empty fallback sequence: drop the whole on_error (a leftover `action: fallback` without steps is invalid)
    return seq.length > 0 ? { ...rest, on_error: { ...step.on_error, steps: seq } } : rest;
  }
  return step;
}

const sameSeq = (a: Step[], b: Step[]) => a.length === b.length && a.every((s, i) => s === b[i]);

/** Apply `fn` to every child sequence of `step`; sequences that did not change are left untouched. */
function mapChildren(step: Step, fn: (seq: Step[], port: Port) => Step[]): Step {
  let out = step;
  for (const port of portsOf(step)) {
    const cur = childSeq(out, port);
    if (!cur) continue;
    const next = fn(cur, port);
    if (!sameSeq(cur, next)) out = setChild(out, port, next);
  }
  return out;
}

/** Rebuild the tree; `fn` sees each step with the ids visible to it (earlier siblings in own and enclosing sequences). */
function rebuild(steps: Step[], visible: string[], fn: (s: Step, visible: string[]) => Step): Step[] {
  const seen = [...visible];
  return steps.map((orig) => {
    const step = mapChildren(fn(orig, seen), (cur, port) => rebuild(cur, port === "fallback" ? [...seen, orig.id] : seen, fn));
    seen.push(step.id);
    return step;
  });
}

export function allSteps(steps: Step[]): Step[] {
  return steps.flatMap((s) => [s, ...portsOf(s).flatMap((p) => allSteps(childSeq(s, p) ?? []))]);
}

export function getSeq(wf: Workflow, path: SeqPath): Step[] | undefined {
  let seq: Step[] | undefined = wf.steps;
  for (let i = 0; i < path.length; i += 2) {
    const port = path[i + 1];
    const owner: Step | undefined = seq?.find((s) => s.id === path[i]);
    if (!owner || !isPort(port)) return undefined;
    seq = childSeq(owner, port);
    if (!seq && port !== "else" && port !== "fallback") return undefined;
    seq ??= []; // empty optional branch
  }
  return seq;
}

export function findStep(wf: Workflow, id: string): { step: Step; path: SeqPath; index: number } | undefined {
  const search = (steps: Step[], path: SeqPath): ReturnType<typeof findStep> => {
    for (const [index, step] of steps.entries()) {
      if (step.id === id) return { step, path, index };
      for (const port of portsOf(step)) {
        const hit = search(childSeq(step, port) ?? [], [...path, step.id, port]);
        if (hit) return hit;
      }
    }
    return undefined;
  };
  return search(wf.steps, []);
}

/** Ids visible to step `id` (valid `stdin.pipe` targets). */
export function visibleSteps(wf: Workflow, id: string): string[] {
  let found: string[] = [];
  rebuild(wf.steps, [], (s, visible) => {
    if (s.id === id) found = [...visible];
    return s;
  });
  return found;
}

/** Drop `stdin.pipe` references to invisible steps. */
function fixPipes(wf: Workflow, warnings: string[]): Workflow {
  const steps = rebuild(wf.steps, [], (s, visible) => {
    if (!isCommand(s) || !s.stdin?.pipe || visible.includes(s.stdin.pipe)) return s;
    warnings.push(`pipe:${s.id}:${s.stdin.pipe}`);
    const { pipe: _p, ...stdin } = s.stdin;
    const { stdin: _s, ...rest } = s;
    return Object.keys(stdin).length > 0 ? { ...rest, stdin } : rest;
  });
  return sameSeq(steps, wf.steps) ? wf : { ...wf, steps };
}

function editSeq(steps: Step[], path: SeqPath, fn: (s: Step[]) => Step[]): Step[] {
  const [id, port, ...rest] = path;
  if (id === undefined) return fn(steps);
  return steps.map((s) => {
    if (s.id !== id || !isPort(port)) return s;
    return setChild(s, port, editSeq(childSeq(s, port) ?? [], rest, fn));
  });
}

const done = (wf: Workflow, warnings: string[] = []): OpResult => ({ wf: fixPipes(wf, warnings), warnings });
const refuse = (wf: Workflow, warning: string): OpResult => ({ wf, warnings: [warning] });
const insertAt = (seq: Step[], step: Step, index?: number): Step[] => {
  const i = index === undefined ? seq.length : Math.max(0, Math.min(index, seq.length));
  return [...seq.slice(0, i), step, ...seq.slice(i)];
};

export function addStep(wf: Workflow, step: Step, path: SeqPath, index?: number): OpResult {
  if (findStep(wf, step.id)) return refuse(wf, `duplicate:${step.id}`);
  if (!getSeq(wf, path)) return refuse(wf, `path:${path.join("/")}`);
  return done({ ...wf, steps: editSeq(wf.steps, path, (s) => insertAt(s, step, index)) });
}

export function removeStep(wf: Workflow, id: string): OpResult {
  const hit = findStep(wf, id);
  if (!hit) return { wf, warnings: [] };
  const gone = new Set(allSteps([hit.step]).map((s) => s.id));
  let next: Workflow = {
    ...wf,
    steps: editSeq(wf.steps, hit.path, (s) => s.filter((x) => x.id !== id)),
  };
  const nodes = wf.layout?.nodes;
  if (nodes && [...gone].some((g) => g in nodes)) {
    const kept = Object.fromEntries(Object.entries(nodes).filter(([k]) => !gone.has(k)));
    next = { ...next, layout: { ...wf.layout, nodes: kept } };
  }
  return done(next); // fixPipes removes pipes onto the removed steps
}

/** Move into another sequence; `index` counts in the target sequence after the step was taken out. */
export function moveStep(wf: Workflow, id: string, path: SeqPath, index?: number): OpResult {
  const hit = findStep(wf, id);
  if (!hit) return { wf, warnings: [] };
  if (path.some((p, i) => i % 2 === 0 && p === id)) return refuse(wf, `cycle:${id}`);
  if (!getSeq(wf, path)) return refuse(wf, `path:${path.join("/")}`);
  if (hit.path.join("/") === path.join("/")) {
    // same sequence: reorder in one step, an interim empty sequence would drop `on_error` (action) of a fallback
    return done({ ...wf, steps: editSeq(wf.steps, path, (s) => insertAt(s.filter((x) => x.id !== id), hit.step, index)) });
  }
  const removed = editSeq(wf.steps, hit.path, (s) => s.filter((x) => x.id !== id));
  return done({ ...wf, steps: editSeq(removed, path, (s) => insertAt(s, hit.step, index)) });
}

/** Move `id` directly behind `afterId`, into the sequence of `afterId`. */
export function moveAfter(wf: Workflow, id: string, afterId: string): OpResult {
  const after = findStep(wf, afterId);
  if (!after || id === afterId) return { wf, warnings: [] };
  const own = findStep(wf, id);
  const sameSeqShift = own && own.path.join("/") === after.path.join("/") && own.index < after.index ? 0 : 1;
  return moveStep(wf, id, after.path, after.index + sameSeqShift);
}

/** Shallow patch of a step; `undefined` values delete the key. The id cannot change here (see renameStep). */
export function updateStep(wf: Workflow, id: string, patch: Record<string, unknown>): OpResult {
  const hit = findStep(wf, id);
  if (!hit) return { wf, warnings: [] };
  const merged: Record<string, unknown> = { ...hit.step, ...patch, id };
  for (const k of Object.keys(merged)) if (merged[k] === undefined) delete merged[k];
  // cast: the patch is built by typed form code; the backend validates the document on every change
  const step = merged as unknown as Step;
  return done({ ...wf, steps: editSeq(wf.steps, hit.path, (s) => s.map((x) => (x.id === id ? step : x))) });
}

export function setLayout(wf: Workflow, id: string, pos: { x: number; y: number }): Workflow {
  return { ...wf, layout: { ...wf.layout, nodes: { ...wf.layout?.nodes, [id]: pos } } };
}

export function setVariables(wf: Workflow, variables: Workflow["variables"]): Workflow {
  const { variables: _v, ...rest } = wf;
  return variables && Object.keys(variables).length > 0 ? { ...rest, variables } : rest;
}

/** Unique id matching ID_PATTERN derived from `base`. */
export function newId(wf: Workflow, base: string): string {
  let b = base.toLowerCase().replace(/[^a-z0-9_]/g, "_");
  if (!/^[a-z]/.test(b)) b = `s_${b}`;
  const taken = new Set(allSteps(wf.steps).map((s) => s.id));
  const free = (c: string) => !taken.has(c) && !RESERVED.has(c);
  if (free(b)) return b;
  for (let n = 2; ; n++) if (free(`${b}_${n}`)) return `${b}_${n}`;
}

function mapStrings(v: unknown, fn: (s: string) => string): unknown {
  if (typeof v === "string") return fn(v);
  if (Array.isArray(v)) return v.map((x) => mapStrings(x, fn));
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, mapStrings(x, fn)]));
  return v;
}

/** Rename a step and every reference: layout, stdin.pipe, condition/foreach source, `{{ id.x }}` templates. */
export function renameStep(wf: Workflow, oldId: string, newName: string): OpResult {
  if (oldId === newName) return { wf, warnings: [] };
  if (!findStep(wf, oldId)) return { wf, warnings: [] };
  if (!ID_PATTERN.test(newName) || RESERVED.has(newName)) return refuse(wf, `invalid:${newName}`);
  if (findStep(wf, newName)) return refuse(wf, `duplicate:${newName}`);
  // `\{{` is an escaped literal and stays; `\\{{` is an escaped backslash plus a real template
  const tpl = new RegExp(`(\\\\*)(\\{\\{\\s*)${oldId}(?=\\.)`, "g");
  const retemplate = (x: string) => x.replace(tpl, (m, bs: string, open: string) => (bs.length % 2 === 1 ? m : `${bs}${open}${newName}`));
  const ref = (s: string) => (s.startsWith(`${oldId}.`) ? newName + s.slice(oldId.length) : s);
  const fix = (s: Step): Step => {
    const o = mapStrings(s, retemplate) as Record<string, unknown>; // same shape, strings only
    if (o.id === oldId) o.id = newName;
    if (typeof o.source === "string") o.source = ref(o.source);
    const c = o.condition as { source: string } | undefined;
    if (c) o.condition = { ...c, source: ref(c.source) };
    const stdin = o.stdin as { pipe?: string } | undefined;
    if (stdin?.pipe === oldId) o.stdin = { ...stdin, pipe: newName };
    return o as unknown as Step; // see updateStep
  };
  const deep = (steps: Step[]): Step[] =>
    steps.map((s) => {
      return mapChildren(fix(s), (cur) => deep(cur));
    });
  let next: Workflow = { ...wf, steps: deep(wf.steps) };
  const nodes = wf.layout?.nodes;
  if (nodes && oldId in nodes) {
    next = { ...next, layout: { ...wf.layout, nodes: Object.fromEntries(Object.entries(nodes).map(([k, v]) => [k === oldId ? newName : k, v])) } };
  }
  return done(next);
}

/** Map a backend validation error path such as `steps[1].then[0].tool` to a step id. */
export function stepIdAtErrorPath(wf: Workflow, path: string): string | undefined {
  let step: Step | undefined;
  let found: string | undefined;
  for (const m of path.matchAll(/(?:^|\.)(steps|then|else|body)\[(\d+)\]/g)) {
    const kw = m[1];
    // `steps` after a step is on_error.steps, i.e. the fallback port
    const port = kw === "steps" ? (step ? "fallback" : undefined) : kw;
    const seq = !step && kw === "steps" ? wf.steps : step && isPort(port) ? childSeq(step, port) : undefined;
    step = seq?.[Number(m[2])];
    if (!step) break;
    found = step.id;
  }
  return found ?? allSteps(wf.steps).find((s) => new RegExp(`\\b${s.id}\\b`).test(path))?.id;
}

/** Output click action: keep stdout of step `id` in variable `<id>_out` via a `set` step right behind it. */
export function captureOutput(wf: Workflow, id: string): OpResult {
  const hit = findStep(wf, id);
  if (!hit) return { wf, warnings: [] };
  const name = `${id}_out`;
  const withVar = name in (wf.variables ?? {}) ? wf : setVariables(wf, { ...wf.variables, [name]: { type: "string" } });
  const stepId = newId(withVar, `${id}_set`);
  const r = addStep(withVar, { id: stepId, kind: "set", variable: name, value: `{{ ${id}.stdout }}` }, hit.path, hit.index + 1);
  return { ...r, created: stepId };
}

/** Output click action: an `if` step right behind step `id` testing that its stdout is not empty. */
export function evaluateOutput(wf: Workflow, id: string): OpResult {
  const hit = findStep(wf, id);
  if (!hit) return { wf, warnings: [] };
  const stepId = newId(wf, `${id}_pruefe`);
  const r = addStep(wf, { id: stepId, kind: "if", condition: { source: `${id}.stdout`, is_empty: false }, then: [] }, hit.path, hit.index + 1);
  return { ...r, created: stepId };
}
