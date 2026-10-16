// SPDX-License-Identifier: AGPL-3.0-or-later
// F-27..F-30 end to end: AI off by default, preview before sending, diff for approval, against a fake OpenAI-style server on 127.0.0.1.
import { expect, test, type Page } from "@playwright/test";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { startServer } from "./server";

const GOOD = 'schema_version: 1\ntool: wc\ndisplay_name: "wc – KI"\n';
const BAD = "schema_version: 1\ntool: wc\nbogus_field: 1\n";

let server: Awaited<ReturnType<typeof startServer>>;
let fake: Server;
let reply = GOOD;
let page: Page;

const openModuleEditor = async () => {
  if (!(await page.getByRole("button", { name: "Neu aus Tool" }).isVisible())) await page.getByRole("button", { name: "Module", exact: true }).click();
  await page.getByLabel("Tool", { exact: true }).fill("wc");
  await page.getByRole("button", { name: "Neu aus Tool" }).click();
  await expect(page.getByRole("textbox", { name: "Rohtext" })).toHaveValue(/tool: wc/);
};
const setAi = async (on: boolean) => {
  await page.getByRole("button", { name: "Einstellungen" }).click();
  const box = page.getByLabel("KI-Funktionen aktivieren");
  await expect(box).toBeVisible();
  await box.setChecked(on);
  if (on) {
    await page.locator("#ai-provider").selectOption("local");
    await page.locator("#ai-l-url").fill(`http://127.0.0.1:${(fake.address() as AddressInfo).port}/v1`); // address() is an AddressInfo for a TCP listener
    await page.locator("#ai-l-model").fill("fake");
  }
  await page.locator("dialog[open]").getByRole("button", { name: "Speichern" }).click();
  await expect(page.locator("dialog[open]").getByRole("status").filter({ hasText: "Gespeichert" })).toBeVisible();
  await page.locator("dialog[open]").getByRole("button", { name: "Schließen" }).click();
};

test.describe.serial("ai", () => {
  test.setTimeout(120_000);
  test.beforeAll(async ({ browser }) => {
    fake = createServer((req, res) => {
      req.resume().on("end", () => {
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ choices: [{ message: { content: reply } }] }));
      });
    });
    await new Promise<void>((ok) => fake.listen(0, "127.0.0.1", ok));
    server = await startServer();
    page = await (await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "de-DE" })).newPage();
    await page.addInitScript(() => localStorage.setItem("wts.helpseen", "1")); // no first-start help dialog
    page.on("dialog", (d) => { void d.accept(); });
    await page.goto(server.url);
    await expect(page.locator("button.tool").first()).toBeVisible({ timeout: 30_000 });
  });
  test.afterAll(() => { server.kill(); fake.close(); });

  test("1) AI off: no buttons, API answers 403", async () => {
    await openModuleEditor();
    await expect(page.getByRole("button", { name: "Mit KI verbessern" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Beispiele mit KI erzeugen" })).toHaveCount(0);
    const token = new URL(server.url).hash.replace("#token=", "");
    const res = await page.request.post(new URL("/api/ai/improve-module", server.url).toString(), { headers: { "X-WTS-Token": token }, data: { tool: "wc" } });
    expect(res.status()).toBe(403);
    expect((await res.json() as { error: string }).error).toBe("ai_disabled");
  });

  test("2) valid answer: preview, send, diff, apply", async () => {
    await setAi(true);
    await openModuleEditor();
    await page.getByRole("button", { name: "Mit KI verbessern" }).click();
    const dlg = page.locator("dialog[open]");
    await expect(dlg.locator("pre").nth(1)).toContainText("wc");
    await dlg.getByRole("button", { name: "Senden" }).click();
    await expect(dlg.getByTestId("ai-valid")).toHaveText("Gültig: ja");
    await expect(dlg.getByTestId("ai-diff")).toContainText("wc – KI");
    await dlg.getByRole("button", { name: "Übernehmen" }).click();
    await expect(page.locator("button.tool", { hasText: "wc – KI" })).toBeVisible();
  });

  test("3) invalid answer: errors, apply disabled", async () => {
    reply = BAD;
    await page.getByRole("button", { name: "Mit KI verbessern" }).click();
    const dlg = page.locator("dialog[open]");
    await dlg.getByRole("button", { name: "Senden" }).click();
    await expect(dlg.getByTestId("ai-valid")).toHaveText("Gültig: nein");
    await expect(dlg.getByTestId("ai-errors").locator("li").first()).toBeVisible();
    await expect(dlg.getByRole("button", { name: "Übernehmen" })).toBeDisabled();
    await dlg.getByRole("button", { name: "Verwerfen" }).click();
  });

  test("4) AI off again: buttons gone", async () => {
    await setAi(false);
    await expect(page.getByRole("button", { name: "Mit KI verbessern" })).toHaveCount(0);
  });
});
