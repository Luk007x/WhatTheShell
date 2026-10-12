// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { exampleTitles, parseRaw, setField, setRowField, textToFlags, toRaw, validRows, type Doc } from "./moduleForm";

const raw = `# comment
schema_version: 1
tool: wc
display_name: wc
options:
  - id: lines
    flags: ["-l"]
    unknown_future: 1
examples:
  - title: Zeilen
    args: { lines: true }
i18n:
  en: { summary: Count }
`;

const doc = (): Doc => {
  const p = parseRaw(raw);
  if (!p.ok) throw new Error(p.error);
  return p.doc;
};

test("form edits keep examples, i18n and unknown row fields", () => {
  let d = setField(doc(), "display_name", "wc – neu");
  d = setRowField(d, "options", 0, "flags", textToFlags("-l, --lines"));
  d = setRowField(d, "options", 0, "label", "Zeilen");
  const back = parseRaw(toRaw(d));
  expect(back.ok && back.doc).toEqual({
    ...doc(),
    display_name: "wc – neu",
    options: [{ id: "lines", flags: ["-l", "--lines"], unknown_future: 1, label: "Zeilen" }],
  });
  expect(exampleTitles(d)).toEqual(["Zeilen"]);
});

test("empty value removes the key; syntax errors are reported", () => {
  expect("display_name" in setField(doc(), "display_name", "")).toBe(false);
  expect(parseRaw("a: [").ok).toBe(false);
  expect(parseRaw("- x").ok).toBe(false);
});

test("scalars that YAML 1.1 reads as date/bool/number stay strings", () => {
  const back = parseRaw(toRaw({ a: "2020-01-01", b: "yes", c: "1e3", n: 3 }));
  expect(back.ok && back.doc).toEqual({ a: "2020-01-01", b: "yes", c: "1e3", n: 3 });
  expect(toRaw({ a: "yes" })).toBe('a: "yes"\n');
});

test("rows that are not mappings are skipped and counted", () => {
  const d = { options: [null, { id: "x" }, "s"] };
  expect(validRows(d, "options")).toEqual({ rows: [{ row: { id: "x" }, index: 1 }], bad: 2 });
  expect(setRowField(d, "options", 0, "label", "L")).toEqual(d);
});
