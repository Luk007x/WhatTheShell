// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { startServer } from "./server";

let server: Awaited<ReturnType<typeof startServer>>;
let page: Page;
const work = mkdtempSync(join(tmpdir(), "wts-e2e-"));
const nodes = () => page.locator(".react-flow__node");
const cmd = () => page.getByTestId("cmd-display");
const node = (name: string) => nodes().filter({ hasText: name }).first();

test.describe.serial("smoke", () => {
  test.beforeAll(async ({ browser }) => {
    server = await startServer();
    page = await (await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "de-DE" })).newPage();
    page.on("dialog", (d) => { void d.accept(); });
    mkdirSync(join(work, "logs"));
    writeFileSync(join(work, "logs", "app.log"), "INFO ok\nERROR disk\n");
  });
  test.afterAll(() => { server.kill(); });

  test("a) Seite, Kopfzeile, Sandbox", async () => {
    await page.goto(server.url);
    await expect(page.getByRole("heading", { name: "WhatTheShell", level: 1 })).toBeVisible();
    await expect(page.getByTestId("sandbox-status")).toHaveAttribute("data-available", "true", { timeout: 10_000 });
    await expect(page.getByText("Bitte über")).toHaveCount(0);
  });

  test("b) Katalog, Hinzufügen", async () => {
    await page.getByRole("searchbox", { name: "Werkzeuge suchen" }).fill("grep");
    const entry = page.locator("button.tool", { hasText: "grep – Text durchsuchen" });
    await expect(entry).toBeVisible();
    await entry.click();
    await expect(page.locator("section.panel", { has: page.locator("#details-h") })).toContainText("grep", { timeout: 10_000 });
    await expect(page.getByText(/Durchsucht Dateien oder Eingaben/).first()).toBeVisible();
    await page.getByRole("button", { name: "Hinzufügen: grep" }).click();
    await expect(nodes()).toHaveCount(1);
    await expect(page.getByLabel(/Suchmuster/)).toBeVisible();
    await expect(page.getByLabel(/Groß-\/Kleinschreibung ignorieren/)).toBeVisible();
  });

  test("c) Formular, Befehlsanzeige", async () => {
    await page.getByLabel(/Suchmuster/).fill("ERROR");
    await page.getByLabel(/Groß-\/Kleinschreibung ignorieren/).check();
    await expect(cmd()).toContainText("--ignore-case");
    await expect(cmd()).toContainText("ERROR");
    await expect(page.getByText("Sicherheitsklasse")).toBeVisible();
    await expect(page.getByRole("region", { name: "Befehl" }).locator("strong")).toHaveText("sicher");
  });

  test("d) Vorschau", async () => {
    await page.getByRole("region", { name: "Vorschau" }).locator("select").selectOption({ label: "Fehlerzeilen finden" });
    await expect(page.getByText("Beispielwerte übernommen")).toBeVisible();
    await page.getByRole("button", { name: "Beispiel ausführen" }).click();
    const prev = page.getByRole("region", { name: "Vorschau" });
    await expect(prev.getByLabel("stdout")).toContainText("disk full", { timeout: 20_000 });
    await expect(prev.getByText(/Exitcode:/)).toContainText("0");
  });

  test("e) wc und Pipe", async () => {
    await page.getByRole("searchbox", { name: "Werkzeuge suchen" }).fill("wc");
    await page.locator("button.tool", { hasText: "wc – " }).click();
    await page.getByRole("button", { name: "Hinzufügen: wc" }).click();
    await expect(nodes()).toHaveCount(2);
    await node("wc").click();
    const form = page.locator(".step-panel");
    await form.getByLabel("Standardeingabe").selectOption("pipe");
    await form.getByLabel("Pipe von Schritt").selectOption("grep");
    await expect(nodes()).toHaveCount(2);
    await expect.poll(() => page.locator(".react-flow__edge").count()).toBeGreaterThanOrEqual(2);
    await expect(cmd()).toContainText("/usr/bin/wc");
    await expect(cmd()).toContainText("< pipe");
  });

  test("f) Bedingung", async () => {
    await page.getByRole("button", { name: "Bedingung", exact: true }).click();
    await expect(nodes()).toHaveCount(3);
    await node("Bedingung").click();
    const form = page.locator(".step-panel");
    await form.getByLabel("Quelle").fill("wc.stdout");
    await form.getByLabel("Operator").selectOption("number_gt");
    await form.getByLabel("Wert").fill("0");
    await expect(form.getByLabel("Quelle")).toHaveValue("wc.stdout");
    await expect(form.getByLabel("Wert")).toHaveValue("0");
  });

  test("g) Trockenlauf", async () => {
    await page.getByRole("button", { name: "Trockenlauf" }).click();
    const plan = page.getByTestId("plan");
    await expect(plan).toContainText("grep");
    await expect(plan).toContainText("wc");
    await expect(plan).toContainText("<safe>");
  });

  test("h) Speichern, Öffnen", async () => {
    await page.getByRole("button", { name: "Speichern", exact: true }).click();
    const dlg = page.getByRole("dialog", { name: "Speichern" });
    await dlg.getByLabel("Dateiname (id)").fill("e2e-test");
    await dlg.getByRole("button", { name: "Speichern", exact: true }).click();
    await expect(dlg).toBeHidden();
    await expect(page.locator(".filemenu .muted strong")).toHaveCount(0); // not dirty any more
    await page.getByRole("button", { name: "Öffnen", exact: true }).click();
    const open = page.getByRole("dialog", { name: "Öffnen" });
    await expect(open.getByRole("button", { name: /e2e-test.*eigene/ })).toBeVisible();
  });

  test("i) log_errors ausführen", async () => {
    const open = page.getByRole("dialog", { name: "Öffnen" });
    await open.getByRole("button", { name: /log_errors.*mitgeliefert/ }).click();
    await expect(nodes()).toHaveCount(6);
    await page.getByRole("button", { name: "Ausführen", exact: true }).click();
    const run = page.getByRole("dialog", { name: "Workflow ausführen?" });
    await run.getByLabel(/Log-Ordner/).fill(work);
    await run.getByLabel("Arbeitsordner", { exact: true }).fill(work);
    await run.getByRole("button", { name: "Workflow ausführen" }).click();
    const confirm = page.getByRole("dialog", { name: "Schritt bestätigen" });
    await expect(confirm).toContainText("tee", { timeout: 20_000 });
    await expect(confirm).toContainText("Vorsicht");
    await confirm.getByRole("button", { name: "Ausführen", exact: true }).click();
    await expect(page.getByTestId("run-status")).toContainText("Erfolgreich", { timeout: 20_000 });
    expect(readFileSync(join(work, "bericht.txt"), "utf8")).toContain("ERROR disk");
  });

  test("j) Sprache", async () => {
    await page.getByLabel("Sprache").selectOption("en");
    await expect(page.getByRole("button", { name: "Open", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save", exact: true })).toBeVisible();
  });
});
