// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test } from "vitest";
import { setLang, t } from "./i18n";

test("missing key returns the key", () => {
  expect(t("does.not.exist")).toBe("does.not.exist");
});

test("languages and params", () => {
  setLang("en");
  expect(t("catalog.fav.add", { name: "ls" })).toBe("Add ls to favorites");
  setLang("de");
  expect(t("catalog.title")).toBe("Katalog");
});

test("de and en have the same keys", async () => {
  const { dicts } = await import("./i18n");
  expect(Object.keys(dicts.en).sort()).toEqual(Object.keys(dicts.de).sort());
});
