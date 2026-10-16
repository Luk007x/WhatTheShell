// SPDX-License-Identifier: AGPL-3.0-or-later
import { expect, test, type Page } from "@playwright/test";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
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
    await page.addInitScript(() => localStorage.setItem("wts.helpseen", "1")); // no first-start help dialog
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

  test("k) Block-Ansicht", async () => {
    const plan = async (re: RegExp) => {
      await page.getByRole("button", { name: "Trockenlauf" }).click();
      await expect(page.getByTestId("plan")).toHaveText(re); // retries until the new plan arrived
      return page.getByTestId("plan").innerText();
    };
    const before = await plan(/^ +ok \[message\]/m); // inside else
    await page.getByRole("button", { name: "Blöcke", exact: true }).click();
    await expect(page.locator("ol.seq.root > li.item")).toHaveCount(4); // 6 steps, 4 on the root level
    const pruefe = page.locator("li.item", { has: page.locator("#blk-pruefe") }).first();
    await expect(pruefe.locator("#blk-bericht")).toBeVisible();
    await expect(pruefe.locator("#blk-ok")).toBeVisible();
    await page.locator("#blk-ok").focus();
    await page.keyboard.press("Alt+ArrowLeft");
    await expect(page.locator("ol.seq.root > li.item")).toHaveCount(5);
    await expect(page.locator("#blk-ok")).toBeFocused();
    await plan(/^ok \[message\]/m); // now on the root level
    await page.getByRole("button", { name: "Graph", exact: true }).click();
    await expect(nodes()).toHaveCount(6);
    await expect(page.getByText("Workflow gültig")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Rückgängig" }).click();
    expect(await plan(/^ +ok \[message\]/m)).toBe(before);
  });

  test("l) Modul-Editor", async () => {
    await page.getByRole("button", { name: "Module", exact: true }).click();
    await page.getByLabel("Tool", { exact: true }).fill("wc");
    await page.getByRole("button", { name: "Neu aus Tool" }).click();
    const raw = page.getByRole("textbox", { name: "Rohtext" });
    await expect(raw).toHaveValue(/tool: wc/);
    await raw.fill((await raw.inputValue()).replace(/^display_name:.*$/m, 'display_name: "wc – E2E"'));
    const editor = page.locator(".mod-editor");
    await editor.getByRole("button", { name: "Speichern", exact: true }).click();
    await expect(editor.getByRole("status")).toContainText("Gespeichert");
    await expect(page.locator(".modules .tools li", { hasText: "wc" }).filter({ hasText: "eigene" })).toHaveCount(1);
    await expect(page.locator("button.tool", { hasText: "wc – E2E" })).toBeVisible();
    await editor.getByRole("button", { name: "Löschen", exact: true }).click();
    await expect(page.locator(".modules .tools li", { hasText: "eigene" })).toHaveCount(0);
    await expect(page.locator("button.tool", { hasText: "wc – E2E" })).toHaveCount(0);
    await page.getByRole("button", { name: "Erstellen", exact: true }).click();
  });

  test("m) Vorlage einfügen", async () => {
    await page.getByRole("button", { name: "Neu", exact: true }).click();
    await expect(nodes()).toHaveCount(0);
    await page.getByRole("searchbox", { name: "Werkzeuge suchen" }).fill("grep");
    await page.locator("button.tool", { hasText: "grep – Text durchsuchen" }).click();
    await page.getByRole("button", { name: "Vorlage einfügen: Treffer zählen" }).click();
    await expect(nodes()).toHaveCount(2);
    await expect(page.locator('input[aria-label="Name"]').first()).toHaveValue("pattern");
  });

  test("n) Drag & Drop, Entf, Kürzel", async () => {
    await page.getByRole("button", { name: "Neu", exact: true }).click();
    await expect(nodes()).toHaveCount(0);
    await page.getByRole("searchbox", { name: "Werkzeuge suchen" }).fill("grep");
    await page.locator("button.tool", { hasText: "grep – Text durchsuchen" }).dragTo(page.locator(".react-flow__pane"), { targetPosition: { x: 300, y: 200 } });
    await expect(nodes()).toHaveCount(1);
    await nodes().first().click();
    await page.keyboard.press("Delete");
    await expect(nodes()).toHaveCount(0);
    await page.locator("body").click({ position: { x: 5, y: 5 } }); // focus off any field
    await page.keyboard.press("Shift+?");
    await expect(page.getByRole("dialog", { name: "Hilfe" }).getByRole("heading", { name: "Tastenkürzel" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Hilfe" })).toBeHidden();
  });

  test("o) Blockansicht: Drop aus Katalog, Entf ohne Rückfrage", async () => {
    await page.getByRole("button", { name: "Neu", exact: true }).click();
    await page.getByRole("button", { name: "Blöcke", exact: true }).click();
    let dialogs = 0;
    page.on("dialog", (d) => { dialogs++; void d.dismiss(); });
    await page.getByRole("searchbox", { name: "Werkzeuge suchen" }).fill("grep");
    await page.locator("button.tool", { hasText: "grep – Text durchsuchen" }).dragTo(page.locator("li.zone").first());
    await expect(page.locator(".blocks .blk")).toHaveCount(1);
    await page.locator(".blocks .blk").first().focus();
    await page.keyboard.press("Delete");
    await expect(page.locator(".blocks .blk")).toHaveCount(0);
    expect(dialogs).toBe(0);
    await page.getByRole("button", { name: "Graph", exact: true }).click();
  });

  test("i2) Hilfe: Kopfzeilenknopf, Abschnitt Tastenkürzel, Esc", async () => {
    await page.getByRole("button", { name: "Hilfe", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Hilfe", level: 2 })).toBeVisible();
    await page.getByRole("tab", { name: "Tastenkürzel" }).click();
    await expect(page.getByRole("cell", { name: "Strg+Z" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator("dialog[open]")).toHaveCount(0);
  });

  test("i3) Handbuch: öffnen, Kapitel, Suche, Zurück", async () => {
    const chapters = existsSync("../docs/manual") ? readdirSync("../docs/manual").filter((f) => /^\d+-.+\.md$/.test(f)) : [];
    await page.getByRole("button", { name: "Handbuch", exact: true }).click();
    const toc = page.getByRole("navigation", { name: "Kapitel" });
    if (chapters.length === 0) {
      await expect(page.getByText("Noch keine Kapitel")).toBeVisible();
    } else {
      await expect(toc.getByRole("button").first()).toBeVisible();
      const word = /[A-Za-zÄÖÜäöüß]{6,}/.exec(readFileSync(`../docs/manual/${chapters[0]}`, "utf8").replace(/^#.*$/m, ""))?.[0] ?? "";
      const before = await toc.getByRole("listitem").count();
      await page.getByRole("searchbox", { name: "Im Handbuch suchen" }).fill(word);
      await expect(toc.getByRole("listitem").first()).toBeVisible();
      await page.getByRole("searchbox", { name: "Im Handbuch suchen" }).fill("qqqqxyzzy");
      await expect(page.getByText("Nichts gefunden.")).toBeVisible();
      expect(before).toBeGreaterThan(0);
    }
    await page.getByRole("button", { name: /Zurück/ }).click();
    await expect(page.getByRole("button", { name: "Hinzufügen: grep" })).toBeVisible();
  });

  test("j) Sprache", async () => {
    await page.getByRole("button", { name: "Einstellungen" }).click();
    await page.getByLabel("Sprache").selectOption("en");
    await page.getByRole("button", { name: "Close" }).click(); // label already switched to English
    await expect(page.getByRole("button", { name: "Open", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save", exact: true })).toBeVisible();
  });

  test("quit button shows closing view (endpoint mocked)", async () => {
    page.removeAllListeners("dialog"); // earlier tests left a dismissing handler
    page.once("dialog", (d) => { void d.accept(); });
    await page.route("**/api/shutdown", (r) => r.fulfill({ status: 202, contentType: "application/json", body: '{"status":"stopping"}' }));
    await page.getByRole("button", { name: /Settings|Einstellungen/ }).click();
    await page.getByRole("button", { name: /WhatTheShell beenden|Quit WhatTheShell/ }).click();
    await expect(page.getByText(/Dieser Tab kann geschlossen werden|This tab can be closed/)).toBeVisible();
  });
});
