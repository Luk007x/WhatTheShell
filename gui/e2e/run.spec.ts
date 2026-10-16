// SPDX-License-Identifier: AGPL-3.0-or-later
// Mode "Ausführen": library, form from variables, dry run, confirmation, live run, recent runs, re-run, saved workflows.
import { expect, test, type Page } from "@playwright/test";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { startServer } from "./server";

let server: Awaited<ReturnType<typeof startServer>>;
let page: Page;
const work = mkdtempSync(join(tmpdir(), "wts-run-"));
const lib = () => page.getByRole("region", { name: "Bibliothek" });
const form = () => page.getByRole("region", { name: "Eingaben" });
const output = () => page.locator(".run-footer");

/** Execute button → workflow dialog → step confirmation for tee → success. */
async function runOnce() {
  await form().getByRole("button", { name: "Ausführen", exact: true }).click();
  const dlg = page.getByRole("dialog", { name: "Workflow ausführen?" });
  await expect(dlg.locator("pre.plan")).toContainText("tee");
  await expect(dlg).toContainText("Höchste Sicherheitsklasse");
  await expect(dlg).toContainText("Vorsicht");
  await dlg.getByRole("button", { name: "Workflow ausführen" }).click();
  const confirm = page.getByRole("dialog", { name: "Schritt bestätigen" });
  await expect(confirm).toContainText("tee", { timeout: 20_000 });
  await confirm.getByRole("button", { name: "Ausführen", exact: true }).click();
  await expect(output().getByTestId("runview-status")).toContainText("Erfolgreich", { timeout: 20_000 });
}

test.describe.serial("run mode", () => {
  test.beforeAll(async ({ browser }) => {
    server = await startServer();
    page = await (await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "de-DE" })).newPage();
    await page.addInitScript(() => localStorage.setItem("wts.helpseen", "1")); // no first-start help dialog
    page.on("dialog", (d) => { void d.accept(); });
    mkdirSync(join(work, "logs"));
    writeFileSync(join(work, "logs", "app.log"), "INFO ok\nERROR disk\n");
    await page.goto(server.url);
  });
  test.afterAll(() => { server.kill(); });

  test("Bibliothek, Formular, Trockenlauf", async () => {
    await page.getByRole("button", { name: "Modus Ausführen" }).click();
    const entry = lib().getByRole("list", { name: "mitgeliefert" }).getByRole("button", { name: /log_errors/ });
    await expect(entry).toBeVisible();
    await entry.click();
    const logdir = form().getByLabel("Log-Ordner");
    await expect(logdir).toHaveValue("./logs");
    await expect(form()).toContainText("relativ zum Arbeitsordner");
    await logdir.fill(join(work, "logs"));
    await form().getByLabel("Arbeitsordner", { exact: true }).fill(work);
    await form().getByRole("button", { name: "Trockenlauf" }).click();
    await expect(output().getByTestId("runview-plan")).toContainText("grep");
  });

  test("Ausführen mit Bestätigung, Verlauf", async () => {
    await runOnce();
    expect(readFileSync(join(work, "bericht.txt"), "utf8")).toContain("ERROR disk");
    const recent = form().getByRole("list", { name: "Letzte Läufe" });
    await expect(recent.getByRole("button", { name: /Fehler in Logs zählen.*Erfolgreich/ })).toHaveCount(1);
  });

  test("Erneut ausführen", async () => {
    rmSync(join(work, "bericht.txt"));
    await output().getByRole("button", { name: "Erneut ausführen" }).click();
    const dlg = page.getByRole("dialog", { name: "Workflow ausführen?" });
    await dlg.getByRole("button", { name: "Workflow ausführen" }).click();
    const confirm = page.getByRole("dialog", { name: "Schritt bestätigen" });
    await confirm.getByRole("button", { name: "Ausführen", exact: true }).click();
    await expect(output().getByTestId("runview-status")).toContainText("Erfolgreich", { timeout: 20_000 });
    expect(existsSync(join(work, "bericht.txt"))).toBe(true);
    await expect(form().getByRole("list", { name: "Letzte Läufe" }).getByRole("button")).toHaveCount(2);
  });

  test("Im Editor öffnen, Verlauf anzeigen, Werte gemerkt", async () => {
    await output().getByRole("button", { name: "Im Editor öffnen" }).click();
    await expect(page.locator(".react-flow__node")).toHaveCount(6);
    await page.getByRole("button", { name: "Modus Ausführen" }).click();
    await form().getByRole("list", { name: "Letzte Läufe" }).getByRole("button").first().click();
    await expect(output()).toContainText("bericht");
    await expect(output().getByTestId("runview-status")).toContainText("Erfolgreich");
    await expect(output().getByRole("button", { name: "Abbrechen" })).toBeDisabled(); // read-only history
    await page.goto("about:blank"); // full reload from the token URL; the mode comes back from localStorage
    await page.goto(server.url);
    await lib().getByRole("button", { name: /log_errors/ }).click();
    await expect(form().getByLabel("Log-Ordner")).toHaveValue(join(work, "logs"));
  });

  test("Gespeicherter Workflow erscheint unter eigene", async () => {
    await page.getByRole("button", { name: "Erstellen", exact: true }).click();
    await page.getByRole("button", { name: "Öffnen", exact: true }).click();
    await page.getByRole("dialog", { name: "Öffnen" }).getByRole("button", { name: /log_errors.*mitgeliefert/ }).click();
    await expect(page.locator(".react-flow__node")).toHaveCount(6);
    await page.getByRole("button", { name: "Speichern", exact: true }).click();
    const dlg = page.getByRole("dialog", { name: "Speichern" });
    await dlg.getByLabel("Dateiname (id)").fill("e2e-lib");
    await dlg.getByRole("button", { name: "Speichern", exact: true }).click();
    await expect(page.getByText("erscheint im Modus Ausführen")).toBeVisible();
    await page.getByRole("button", { name: "Modus Ausführen" }).click();
    await expect(lib().getByRole("list", { name: "eigene" }).getByRole("button", { name: /e2e-lib/ })).toBeVisible();
  });
});
