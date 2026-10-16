// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { parseChoices } from "./VariablesPanel";

describe("parseChoices", () => {
  it("splits, trims and drops empty entries", () => expect(parseChoices(" a, b ,,c,")).toEqual(["a", "b", "c"]));
  it("returns undefined when empty", () => expect(parseChoices(" , ")).toBeUndefined());
});
