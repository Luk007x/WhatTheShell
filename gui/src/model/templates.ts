// SPDX-License-Identifier: AGPL-3.0-or-later
// Insert a workflow template (module `templates[]`) into the current document.
import type { Workflow } from "../types/workflow";
import { allSteps, newId, renameStep, setVariables, type OpResult } from "./ops";

/**
 * Empty workflow: the template replaces the steps and name; variables and layout of both are merged (template wins).
 * Otherwise its steps are appended at the root, colliding ids are renamed (with all references) and variables
 * are merged; existing variables win, a differing template definition yields the warning `varconflict:<name>`.
 */
export function mergeTemplate(wf: Workflow, tpl: Workflow): OpResult {
  if (wf.steps.length === 0) {
    let out: Workflow = tpl;
    if (wf.variables || tpl.variables) out = setVariables(out, { ...wf.variables, ...tpl.variables });
    if (wf.layout || tpl.layout) out = { ...out, layout: { ...wf.layout, ...tpl.layout, nodes: { ...wf.layout?.nodes, ...tpl.layout?.nodes } } };
    return { wf: out, warnings: [] };
  }
  const taken = () => new Set(allSteps(wf.steps).map((s) => s.id));
  let cur = tpl;
  for (const { id } of allSteps(tpl.steps)) {
    if (!taken().has(id)) continue;
    const next = newId({ ...wf, steps: [...wf.steps, ...cur.steps] }, id);
    cur = renameStep(cur, id, next).wf;
  }
  const warnings = Object.entries(cur.variables ?? {})
    .filter(([k, v]) => wf.variables && k in wf.variables && JSON.stringify(wf.variables[k]) !== JSON.stringify(v))
    .map(([k]) => `varconflict:${k}`);
  const merged = setVariables({ ...wf, steps: [...wf.steps, ...cur.steps] }, { ...cur.variables, ...wf.variables });
  return { wf: merged, warnings };
}
