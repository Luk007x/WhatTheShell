// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { askedVariables, withoutAsked, initialValues, matchesPattern, storable, toOverrides, validate } from "./runForm";

const entry = {
  variables: {
    logdir: { type: "path" as const, default: "./logs", label: "Log-Ordner" },
    n: { type: "int" as const, required: true, min: 1, max: 5 },
    f: { type: "float" as const },
    on: { type: "bool" as const, default: true },
    token: { type: "secret" as const },
    text: { type: "string" as const },
    level: { type: "enum" as const, choices: ["debug", "info"], default: "info" },
  },
};
const base = { logdir: "", n: "2", f: "", on: false, token: "", text: "", level: "info" };

test("initialValues: defaults, stored values, secrets never restored", () => {
  expect(initialValues(entry, null)).toEqual({ logdir: "./logs", n: "", f: "", on: true, token: "", text: "", level: "info" });
  expect(initialValues(entry, { logdir: "/tmp", on: false, token: "x", n: 3 })).toMatchObject({ logdir: "/tmp", n: "", on: false, token: "" });
});

test("validate: required, int, float", () => {
  expect(validate(entry, { ...base, n: "" })).toEqual({ n: "required" });
  expect(validate(entry, { ...base, n: "1.5", f: "abc" })).toEqual({ n: "int", f: "float" });
  expect(validate(entry, { ...base, f: "1e3" })).toEqual({});
  for (const ok of ["1", "-1.5", ".5", "+2.", "3E-2"]) expect(validate(entry, { ...base, f: ok }), ok).toEqual({});
  for (const bad of ["0x10", "Infinity", "1e", ".", "1.2.3", "1 2"]) expect(validate(entry, { ...base, f: bad }), bad).toEqual({ f: "float" });
});

test("validate: choices and bounds", () => {
  expect(validate(entry, { ...base, level: "warn" })).toEqual({ level: "choice" });
  expect(validate(entry, { ...base, n: "0" })).toEqual({ n: "min" });
  expect(validate(entry, { ...base, n: "6" })).toEqual({ n: "max" });
  expect(validate(entry, { ...base, n: "5" })).toEqual({});
});

test("toOverrides: strings only, empty dropped, trims only int/float/path", () => {
  expect(toOverrides(entry, { logdir: " /x ", n: " 2 ", f: "", on: false, text: "  a b ", token: " s3cret ", level: "info" }))
    .toEqual({ logdir: "/x", n: "2", on: "false", text: "  a b ", token: " s3cret ", level: "info" });
});

test("storable: whitelist of declared non-secret variables", () => {
  expect(storable(entry, { logdir: "/x", token: "geheim", stray: "y" })).toEqual({ logdir: "/x" });
});

test("validate: pattern is a full match, invalid regex is left to the backend", () => {
  const e = { variables: { id: { type: "string" as const, pattern: "[a-z]+\\d" } } };
  expect(validate(e, { id: "ab1" })).toEqual({});
  expect(validate(e, { id: "ab1x" })).toEqual({ id: "pattern" });
  expect(validate(e, { id: "" })).toEqual({});
  expect(matchesPattern("(", "x")).toBe(true);
});

test("askedVariables walks nested steps; withoutAsked and toOverrides leave them out", () => {
  const wf = { steps: [
    { id: "i", kind: "if", condition: { source: "x", is_empty: false }, then: [{ id: "q", kind: "ask", title: "", text: "", fields: ["a"], buttons: ["OK"], button_variable: "b" }] },
    { id: "f", kind: "foreach", source: "x", body: [{ id: "q2", kind: "ask", title: "", text: "", fields: ["c"] }] },
  ] } as unknown as Parameters<typeof askedVariables>[0];
  const asked = askedVariables(wf);
  expect([...asked].sort()).toEqual(["a", "b", "c"]);
  const entry = withoutAsked({ variables: { a: { required: true }, d: {} } }, asked);
  expect(Object.keys(entry.variables)).toEqual(["d"]);
  expect(validate(entry, { d: "" })).toEqual({});
  expect(toOverrides(entry, { a: "x", d: "y" })).toEqual({ d: "y" });
});
