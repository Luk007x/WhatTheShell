// SPDX-License-Identifier: AGPL-3.0-or-later
// WCAG 2.1 AA audit with axe over the main states, plus a mouse-free keyboard run.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { startServer } from "./server";

let server: Awaited<ReturnType<typeof startServer>>;
let page: Page;

const audit = async (name: string) => {
  const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const summary = res.violations.map((v) => `${v.id} (${v.nodes.length}): ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
  expect(summary, name).toEqual([]);
};

test.describe.serial("a11y", () => {
  test.setTimeout(180_000); // the catalog lists every executable on PATH, axe needs a while
  test.beforeAll(async ({ browser }) => {
    server = await startServer();
    page = await (await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "de-DE" })).newPage();
    page.on("dialog", (d) => { void d.accept(); });
    await page.goto(server.url);
    await expect(page.getByTestId("sandbox-status")).toHaveAttribute("data-available", "true", { timeout: 10_000 });
    await expect(page.locator("button.tool").first()).toBeVisible();
  });
  test.afterAll(() => { server.kill(); });

  test("start (catalog)", async () => { await audit("start"); });

  test("keyboard only: add grep and reach the form", async () => {
    await page.goto(server.url); // a reload would lose the token (fragment is removed)
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Zum Hauptbereich springen" })).toBeFocused();
    await page.getByRole("searchbox", { name: "Werkzeuge suchen" }).focus();
    await page.keyboard.type("grep");
    await expect(page.locator("button.tool", { hasText: "grep – Text durchsuchen" })).toBeVisible();
    await page.keyboard.press("ArrowDown");
    await expect(page.locator("button.tool").first()).toBeFocused();
    await page.keyboard.press("Enter");
    const add = page.getByRole("button", { name: "Hinzufügen: grep" });
    await expect(add).toBeEnabled({ timeout: 10_000 });
    await add.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".react-flow__node")).toHaveCount(1);
    await expect(page.getByLabel(/Suchmuster/)).toBeVisible();
    await page.locator(".react-flow__node").first().focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".step-panel")).toBeVisible();
  });

  test("step selected (form)", async () => { await audit("form"); });

  test("block view", async () => {
    await page.getByRole("button", { name: "Blöcke", exact: true }).click();
    await expect(page.locator("#blk-grep")).toBeVisible();
    await page.getByRole("button", { name: /Einfügen in Hauptfolge/ }).click();
    await audit("blocks with add list");
    await page.locator("#blk-grep").focus();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Graph", exact: true }).click();
  });

  test("run panel with plan", async () => {
    await page.getByRole("button", { name: "Trockenlauf" }).click();
    await expect(page.getByTestId("plan")).toContainText("grep");
    await audit("run panel");
  });

  test("module editor", async () => {
    await page.getByRole("button", { name: "Module", exact: true }).click();
    await page.locator(".modules .tools button", { hasText: "grep" }).first().click();
    await expect(page.getByRole("textbox", { name: "Rohtext" })).toBeVisible();
    await audit("modules raw");
    await page.getByRole("tab", { name: "Formular" }).click();
    await audit("modules form");
    await page.getByRole("button", { name: "Erstellen", exact: true }).click();
  });

  test("settings modal and focus return", async () => {
    const gear = page.getByRole("button", { name: "Einstellungen" });
    await gear.click();
    await expect(page.getByRole("dialog", { name: "Einstellungen" })).toBeVisible();
    await audit("settings");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(gear).toBeFocused();
  });

  test("run mode: library, form, recent runs", async () => {
    const work = mkdtempSync(join(tmpdir(), "wts-a11y-")); // no logs: the run takes the else branch, no step confirmation
    await page.getByRole("button", { name: "Modus Ausführen" }).click();
    await page.getByRole("region", { name: "Bibliothek" }).getByRole("button", { name: /log_errors/ }).click();
    const form = page.getByRole("region", { name: "Eingaben" });
    await form.getByLabel("Log-Ordner").fill(work);
    await form.getByLabel("Arbeitsordner", { exact: true }).fill(work);
    await audit("run mode form");
    await form.getByRole("button", { name: "Ausführen", exact: true }).click();
    const dlg = page.getByRole("dialog", { name: "Workflow ausführen?" });
    await expect(dlg.locator("pre.plan")).toContainText("grep");
    await audit("run mode dialog");
    await dlg.getByRole("button", { name: "Workflow ausführen" }).click();
    await expect(page.getByTestId("runview-status")).toContainText(/Erfolgreich|Fehlgeschlagen/, { timeout: 20_000 });
    await expect(form.getByRole("list", { name: "Letzte Läufe" }).getByRole("button")).toHaveCount(1);
    await audit("run mode output and recent runs");
    await page.getByRole("button", { name: "Erstellen", exact: true }).click();
  });
});
