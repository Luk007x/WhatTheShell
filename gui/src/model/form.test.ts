// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import type { OptionSpec } from "../types/api";
import { argsFromForm, conditionOperator, conditionWith, fieldKind, firstSentence, sortOptions } from "./form";

const opt = (o: Partial<OptionSpec> & { id: string }): OptionSpec => ({ flags: ["--" + o.id], type: "string", ...o });

test("fieldKind", () => {
  expect(fieldKind(opt({ id: "a", type: "bool" }))).toBe("checkbox");
  expect(fieldKind(opt({ id: "a", type: "int" }))).toBe("number");
  expect(fieldKind(opt({ id: "a", type: "int" }), "{{ var.n }}")).toBe("text");
  expect(fieldKind(opt({ id: "a", type: "enum", choices: ["x"] }))).toBe("select");
  expect(fieldKind(opt({ id: "a", multiple: true }))).toBe("textarea");
  expect(fieldKind(opt({ id: "a", nargs: 2 }))).toBe("tuple");
  expect(fieldKind(opt({ id: "a", type: "secret" }))).toBe("password");
  expect(fieldKind(opt({ id: "a", type: "path" }))).toBe("path");
});

test("sortOptions groups, importance and search", () => {
  const r = sortOptions([
    opt({ id: "a" }),
    opt({ id: "b", group: "G", importance: "normal" }),
    opt({ id: "c", group: "G", importance: "common" }),
    opt({ id: "d", importance: "rare" }),
  ]);
  expect(r.groups.map((g) => g.name)).toEqual(["G", null]);
  expect(r.groups[0]?.options.map((o) => o.id)).toEqual(["c", "b"]);
  expect(r.rare.map((o) => o.id)).toEqual(["d"]);
  expect(sortOptions([opt({ id: "a", help: "Zeigt FOO" })], "foo").groups).toHaveLength(1);
  expect(sortOptions([opt({ id: "a" })], "zzz").groups).toHaveLength(0);
});

test("argsFromForm", () => {
  const num = opt({ id: "n", type: "int" });
  expect(argsFromForm({}, num, "3")).toEqual({ n: 3 });
  expect(argsFromForm({ n: 3 }, num, "")).toEqual({});
  expect(argsFromForm({}, num, "{{ var.x }}")).toEqual({ n: "{{ var.x }}" });
  expect(argsFromForm({ b: true }, opt({ id: "b", type: "bool" }), false)).toEqual({});
  expect(argsFromForm({}, opt({ id: "m", multiple: true }), ["a", "", "b"])).toEqual({ m: ["a", "b"] });
  expect(argsFromForm({}, opt({ id: "t", nargs: 2 }), ["", ""])).toEqual({});
});

test("firstSentence", () => {
  expect(firstSentence("Erste Zeile. Zweite.")).toBe("Erste Zeile.");
  expect(firstSentence("ohne Punkt")).toBe("ohne Punkt");
  expect(firstSentence(null)).toBe("");
});

test("condition operator is exclusive", () => {
  const c = conditionWith({ source: "a.stdout" }, "number_gt", "3");
  expect(c).toEqual({ source: "a.stdout", number_gt: 3 });
  expect(conditionOperator(c)).toBe("number_gt");
  expect(conditionWith({ source: "x" }, "is_empty", true)).toEqual({ source: "x", is_empty: true });
});
