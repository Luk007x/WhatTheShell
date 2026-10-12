// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import type { ToolSummary } from "../types/api";
import { categoryClass, groupTools } from "./groupTools";

const tools: ToolSummary[] = [
  { name: "rm", path: "/bin/rm", category: "Dateien", summary: "remove" },
  { name: "ls", path: "/bin/ls", category: "Dateien", display_name: "Auflisten" },
  { name: "foo", path: "/bin/foo" },
  { name: "awk", path: "/bin/awk", category: "Text" },
];

test("groups by category, uncategorised last, sorted by label", () => {
  const g = groupTools(tools, "");
  expect(g.map((x) => x.category)).toEqual(["Dateien", "Text", ""]);
  expect(g[0]?.tools.map((x) => x.name)).toEqual(["ls", "rm"]);
});

test("search matches name, display name and summary, case-insensitive", () => {
  expect(groupTools(tools, "AUFLIST").flatMap((x) => x.tools.map((y) => y.name))).toEqual(["ls"]);
  expect(groupTools(tools, "remove").flatMap((x) => x.tools.map((y) => y.name))).toEqual(["rm"]);
  expect(groupTools(tools, "zzz")).toEqual([]);
});

test("category colour is stable and bounded", () => {
  expect(categoryClass("Text")).toBe(categoryClass("Text"));
  expect(categoryClass("Dateien")).toMatch(/^cat-[0-7]$/);
  expect(categoryClass(null)).toBe("cat-none");
});
