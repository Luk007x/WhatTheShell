// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure helpers of the workflow library: source filter and import file name.
import type { WorkflowListItem, WorkflowSource } from "../types/api";

export type LibFilter = "all" | "user" | "bundled" | "project";
export const FILTERS: LibFilter[] = ["all", "user", "bundled", "project"];
export const FILTER_KEY = "wts.libfilter";
export const MAX_IMPORT_BYTES = 1024 * 1024;
export const IMPORT_SUFFIX = ".workflow.yaml";

export const matchesFilter = (f: LibFilter, source: WorkflowSource): boolean => f === "all" || f === source;

export function loadFilter(): LibFilter {
  try {
    const v = localStorage.getItem(FILTER_KEY);
    return FILTERS.find((f) => f === v) ?? "all";
  } catch { return "all"; }
}

/** `foo.yaml` / `foo.yml` / `foo` → `foo.workflow.yaml`; a name that already ends in `.workflow.yaml` stays. */
export function proposeImportName(fileName: string): string {
  const name = fileName.trim();
  if (name.endsWith(IMPORT_SUFFIX)) return name;
  return `${name.replace(/\.(ya?ml)$/i, "")}${IMPORT_SUFFIX}`;
}

export const needsAccept = (x: Pick<WorkflowListItem, "integrity">): boolean => x.integrity === "modified" || x.integrity === "unstamped";
