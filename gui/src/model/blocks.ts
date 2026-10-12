// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure logic of the block view (D-010): nested tree derived from the document, keyboard move targets.
// All mutations go through ops.ts (moveStep, addStep, removeStep); nothing here edits the document.
import { t } from "../i18n";
import type { Workflow } from "../types/workflow";
import { childSeq, findStep, getSeq, newId, portsOf, type Port, type SeqPath, type Step } from "./ops";

export interface Slot { port: Port; path: SeqPath; blocks: Block[] }
export interface Block { step: Step; path: SeqPath; index: number; slots: Slot[] }
export interface BlockTree { blocks: Block[] }
/** Target for `moveStep`; no index = append at the end. */
export interface Move { path: SeqPath; index?: number }

export function toBlocks(wf: Workflow): BlockTree {
  const build = (steps: Step[], path: SeqPath): Block[] =>
    steps.map((step, index) => ({
      step,
      path,
      index,
      slots: portsOf(step).map((port) => {
        const sub = [...path, step.id, port];
        return { port, path: sub, blocks: build(childSeq(step, port) ?? [], sub) };
      }),
    }));
  return { blocks: build(wf.steps, []) };
}

const stepName = (s: Step) => s.label ?? s.id;

/** Keyboard/menu actions for step `id`: one step up/down, into the slots of the directly preceding step, out behind the owner. */
export function moveTargets(wf: Workflow, id: string): { up: Move | null; down: Move | null; into: (Move & { label: string })[]; out: Move | null } {
  const hit = findStep(wf, id);
  if (!hit) return { up: null, down: null, into: [], out: null };
  const seq = getSeq(wf, hit.path) ?? [];
  const prev = seq[hit.index - 1];
  const ownerId = hit.path[hit.path.length - 2];
  const owner = ownerId === undefined ? undefined : findStep(wf, ownerId);
  return {
    up: hit.index > 0 ? { path: hit.path, index: hit.index - 1 } : null,
    down: hit.index < seq.length - 1 ? { path: hit.path, index: hit.index + 1 } : null,
    into: prev ? portsOf(prev).map((port) => ({ path: [...hit.path, prev.id, port], label: `${stepName(prev)}: ${t(`blocks.slot.${port}`)}` })) : [],
    out: owner ? { path: owner.path, index: owner.index + 1 } : null,
  };
}

/** A step must not be dropped into its own sub-sequence. */
export const canDrop = (path: SeqPath, id: string): boolean => !path.some((p, i) => i % 2 === 0 && p === id);

/** Drop zone index (counted with the step still in place) -> `moveStep` index (step already taken out). */
export function dropIndex(wf: Workflow, id: string, path: SeqPath, zone: number): number {
  const hit = findStep(wf, id);
  return hit && hit.path.join("/") === path.join("/") && hit.index < zone ? zone - 1 : zone;
}

/** Human-readable place of a sequence, for labels and screen reader messages. */
export function placeOfPath(wf: Workflow, path: SeqPath): string {
  const port = path[path.length - 1];
  const owner = path[path.length - 2];
  const step = owner === undefined ? undefined : findStep(wf, owner)?.step;
  return step && port ? `${stepName(step)}: ${t(`blocks.slot.${port}`)}` : t("blocks.root");
}

export function placeOf(wf: Workflow, id: string): string {
  const hit = findStep(wf, id);
  return hit ? t("blocks.pos", { where: placeOfPath(wf, hit.path), n: hit.index + 1 }) : "";
}

export const CONTROL_KINDS = ["if", "foreach", "set", "wait", "message", "abort"] as const;
export type ControlKind = (typeof CONTROL_KINDS)[number];

/** New control step with defaults (same as the graph toolbar). */
export function controlStep(wf: Workflow, kind: ControlKind): Step {
  const id = newId(wf, kind);
  const last = wf.steps[wf.steps.length - 1]?.id;
  const src = last ? `${last}.stdout` : "";
  switch (kind) {
    case "if": return { id, kind, condition: { source: src, is_empty: false }, then: [] };
    case "foreach": return { id, kind, source: src, body: [] };
    case "set": return { id, kind, variable: Object.keys(wf.variables ?? {})[0] ?? "", value: "" };
    case "wait": return { id, kind, seconds: 1 };
    case "message": return { id, kind, text: "" };
    case "abort": return { id, kind };
  }
}
