// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import type { WorkflowIntegrity } from "../types/api";
import { matchesFilter, needsAccept, proposeImportName } from "./libraryImport";

test("proposeImportName", () => {
  expect(proposeImportName("foo.yaml")).toBe("foo.workflow.yaml");
  expect(proposeImportName("foo.YML")).toBe("foo.workflow.yaml");
  expect(proposeImportName("foo.workflow.yaml")).toBe("foo.workflow.yaml");
  expect(proposeImportName("foo")).toBe("foo.workflow.yaml");
});

test("filter predicate", () => {
  expect(matchesFilter("all", "bundled")).toBe(true);
  expect(matchesFilter("user", "user")).toBe(true);
  expect(matchesFilter("user", "project")).toBe(false);
});

test("needsAccept only for modified/unstamped", () => {
  const all: WorkflowIntegrity[] = ["ok", "modified", "unstamped", "invalid"];
  expect(all.map((integrity) => needsAccept({ integrity }))).toEqual([false, true, true, false]);
});
