// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ToolSummary } from "../types/api";

export const OTHER = "";

export interface Group {
  /** Category name; `OTHER` ("") for tools without category. */
  category: string;
  tools: ToolSummary[];
}

export const label = (tool: ToolSummary): string => tool.display_name ?? tool.name;

/** Filter by query (name, display name, summary), group by category sorted by name, uncategorised last. */
export function groupTools(tools: ToolSummary[], query: string): Group[] {
  const q = query.trim().toLowerCase();
  const hits = tools.filter(
    (x) => !q || [x.name, x.display_name, x.summary].some((s) => s?.toLowerCase().includes(q)),
  );
  const byCat = new Map<string, ToolSummary[]>();
  for (const tool of hits) {
    const key = tool.category ?? OTHER;
    byCat.set(key, [...(byCat.get(key) ?? []), tool]);
  }
  return [...byCat.entries()]
    .sort(([a], [b]) => (a === OTHER ? 1 : b === OTHER ? -1 : a.localeCompare(b)))
    .map(([category, list]) => ({
      category,
      tools: list.sort((a, b) => label(a).localeCompare(label(b))),
    }));
}
