// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { initialValues, storable, toOverrides, validate } from "./runForm";

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
