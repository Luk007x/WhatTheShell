// SPDX-License-Identifier: AGPL-3.0-or-later
// Details column: open in a window and back, axe check of the window.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { startServer } from "./server";

let server: Awaited<ReturnType<typeof startServer>>;
let page: Page;

test.describe.serial("details window", () => {
  test.setTimeout(120_000);
  test.beforeAll(async ({ browser }) => {
    server = await startServer();
    page = await (await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "de-DE" })).newPage();
    await page.addInitScript(() => localStorage.setItem("wts.helpseen", "1"));
    await page.goto(server.url);
    await expect(page.locator("button.tool").first()).toBeVisible({ timeout: 30_000 });
  });
  test.afterAll(() => { server.kill(); });

  test("expand, audit, collapse", async () => {
    await page.getByRole("searchbox", { name: "Werkzeuge suchen" }).fill("grep");
    await page.locator("button.tool", { hasText: "grep – Text durchsuchen" }).click();
    await page.getByRole("button", { name: "Hinzufügen: grep" }).click();
    await expect(page.locator(".step-panel")).toBeVisible();
    await page.getByRole("button", { name: "Details im Fenster öffnen" }).click();
    const dlg = page.getByRole("dialog", { name: "Details" });
    await expect(dlg).toBeVisible();
    await expect(dlg.getByLabel("Schritt-id").first()).toBeVisible();
    await expect(page.locator(".app-main .step-panel")).toHaveCount(0);
    const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(res.violations.map((v) => v.id)).toEqual([]);
    await dlg.getByRole("button", { name: "Zurück in die Seitenleiste" }).click();
    await expect(dlg).toBeHidden();
    await expect(page.locator(".app-main").getByLabel("Schritt-id").first()).toBeVisible();
  });
});
