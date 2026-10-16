// SPDX-License-Identifier: AGPL-3.0-or-later
// Terminal step: `cat` in the embedded terminal (bwrap + PTY), typed input echoes, Ctrl+D ends it with exit 0.
import { expect, test, type Page } from "@playwright/test";
import { startServer } from "./server";

let server: Awaited<ReturnType<typeof startServer>>;
let page: Page;

test.describe.serial("terminal step", () => {
  test.beforeAll(async ({ browser }) => {
    server = await startServer();
    page = await (await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "de-DE" })).newPage();
    await page.addInitScript(() => localStorage.setItem("wts.helpseen", "1")); // no first-start help dialog
    page.on("dialog", (d) => { void d.accept(); });
    await page.goto(server.url);
  });
  test.afterAll(() => { server.kill(); });

  test("cat im Terminal: Eingabe, Echo, Strg+D", async () => {
    await expect(page.getByTestId("sandbox-status")).not.toHaveAttribute("data-available", "unknown", { timeout: 10_000 });
    test.skip((await page.getByTestId("sandbox-status").getAttribute("data-available")) !== "true", "bwrap fehlt: Terminal-Schritte sind ohne Sandbox gesperrt (SECURITY.md 7.2)");

    await page.getByRole("searchbox", { name: "Werkzeuge suchen" }).fill("cat");
    await page.locator("button.tool", { hasText: /^cat\b/ }).first().click();
    await page.getByRole("button", { name: "Hinzufügen: cat" }).click();
    await expect(page.locator(".react-flow__node")).toHaveCount(1);
    await page.getByLabel("Als Terminal-Schritt ausführen").check();

    await page.getByRole("button", { name: "Ausführen", exact: true }).click();
    const dlg = page.getByRole("dialog", { name: "Workflow ausführen?" });
    await expect(dlg.locator("pre.plan")).toContainText("cat");
    await expect(dlg.getByLabel(/Terminal-Ausgabe als Transkript speichern/)).not.toBeChecked(); // default off
    await dlg.getByRole("button", { name: "Workflow ausführen" }).click();
    const confirm = page.getByRole("dialog", { name: "Schritt bestätigen" });
    await expect(confirm).toContainText("cat", { timeout: 20_000 });
    await confirm.getByRole("button", { name: "Ausführen", exact: true }).click();

    const term = page.getByRole("group", { name: /^Terminal: .*cat$/ });
    await expect(term).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Ausgabe wird gespeichert")).toHaveCount(0);
    await expect(term.locator(".xterm-helper-textarea")).toBeFocused();
    await page.keyboard.type("hi");
    await page.keyboard.press("Enter");
    await expect(term.locator(".xterm-rows")).toContainText("hi");
    await page.keyboard.press("Control+D");

    await expect(page.getByTestId("run-status")).toContainText("Erfolgreich", { timeout: 20_000 });
    await expect(page.getByText("Terminal beendet (Exit 0)")).toBeVisible();
    await expect(term.locator(".xterm-rows")).toContainText("hi"); // content stays, read-only
    await page.getByRole("button", { name: "Schließen", exact: true }).click();
    await expect(term).toHaveCount(0);
  });
});
