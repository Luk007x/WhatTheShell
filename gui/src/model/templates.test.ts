// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { logErrors } from "./fixture";
import { allSteps } from "./ops";
import { mergeTemplate } from "./templates";
import type { Workflow } from "../types/workflow";

const tpl: Workflow = {
  schema_version: 1,
  name: "Treffer zählen",
  variables: { pattern: { type: "string", default: "ERROR" }, logdir: { type: "path", default: "." } },
  steps: [
    { id: "suche", tool: "grep", args: { patterns: "{{ var.pattern }}" } },
    { id: "meldung", kind: "message", text: "{{ suche.stdout }}" },
  ],
};

test("empty workflow is replaced, name taken over", () => {
  const r = mergeTemplate({ schema_version: 1, name: "", steps: [] }, tpl);
  expect(r.wf).toEqual(tpl);
});

test("empty workflow: variables and layout are merged, template wins", () => {
  const empty: Workflow = { schema_version: 1, name: "", steps: [], variables: { pattern: { type: "int" }, mine: { type: "string" } }, layout: { nodes: { a: { x: 1, y: 2 } } } };
  const r = mergeTemplate(empty, { ...tpl, layout: { nodes: { suche: { x: 0, y: 0 } } } }).wf;
  expect(Object.keys(r.variables ?? {}).sort()).toEqual(["logdir", "mine", "pattern"]);
  expect(r.variables?.pattern).toEqual(tpl.variables?.pattern);
  expect(r.layout?.nodes).toEqual({ a: { x: 1, y: 2 }, suche: { x: 0, y: 0 } });
});

test("non-empty: appended, collision suche renamed with references, variables merged", () => {
  const res = mergeTemplate(logErrors, tpl);
  const r = res.wf;
  expect(res.warnings).toEqual(["varconflict:logdir"]); // same name, different definition
  expect(allSteps(r.steps).map((s) => s.id)).toEqual(["finde", "suche", "zaehle", "pruefe", "bericht", "ok", "suche_2", "meldung"]);
  expect(r.steps.at(-1)).toEqual({ id: "meldung", kind: "message", text: "{{ suche_2.stdout }}" });
  expect(r.name).toBe(logErrors.name);
  expect(r.variables).toEqual({ pattern: tpl.variables?.pattern, logdir: logErrors.variables?.logdir });
});

test("differing variable definition warns, existing one stays", () => {
  const base: Workflow = { ...logErrors, variables: { pattern: { type: "int" } } };
  const res = mergeTemplate(base, tpl);
  expect(res.warnings).toEqual(["varconflict:pattern"]);
  expect(res.wf.variables?.pattern).toEqual({ type: "int" });
});
