// SPDX-License-Identifier: AGPL-3.0-or-later
// Layout check (no overlapping areas at 1280×720, also with font size "large") and design screenshots e2e-results/design-*.png.
import { expect, test, type Page } from "@playwright/test";
import { startServer } from "./server";

let server: Awaited<ReturnType<typeof startServer>>;
let page: Page;
const shot = (name: string) => page.screenshot({ path: `e2e-results/design-${name}.png` });

/** The grid areas must not overlap and must stay inside the viewport. */
async function noOverlap(label: string, sections = 3) {
  const areas = Array.from({ length: sections }, (_, i) => `.app-main:visible > section:nth-of-type(${i + 1})`);
  const sel = [".app-header", ".modebar", ...areas, ".app-footer:visible"];
  const boxes = await Promise.all(sel.map(async (s) => ({ s, b: await page.locator(s).first().boundingBox() })));
  const vp = page.viewportSize() ?? { width: 0, height: 0 };
  for (const { s, b } of boxes) {
    expect(b, `${label}: ${s} visible`).not.toBeNull();
    if (!b) continue;
    expect(b.x + b.width, `${label}: ${s} inside width`).toBeLessThanOrEqual(vp.width + 1);
    expect(b.y + b.height, `${label}: ${s} inside height`).toBeLessThanOrEqual(vp.height + 1);
  }
  for (const [i, { s: a, b: p }] of boxes.entries()) {
    for (const { s: c, b: q } of boxes.slice(i + 1)) {
      if (!p || !q) continue;
      const ix = Math.min(p.x + p.width, q.x + q.width) - Math.max(p.x, q.x);
      const iy = Math.min(p.y + p.height, q.y + q.height) - Math.max(p.y, q.y);
      expect(ix > 1 && iy > 1, `${label}: ${a} overlaps ${c}`).toBe(false);
    }
  }
  // buttons of the header and the canvas / run toolbars must not overlap each other
  for (const bar of [".app-header", ".panel.canvas > .toolbar", ".run-footer .toolbar", ".runform .tb-group"]) {
    const rects = await page.locator(`${bar} button:visible`).evaluateAll((els) => els.map((e) => e.getBoundingClientRect().toJSON() as { x: number; y: number; width: number; height: number }));
    for (const [i, p] of rects.entries()) {
      for (const q of rects.slice(i + 1)) {
        const ix = Math.min(p.x + p.width, q.x + q.width) - Math.max(p.x, q.x);
        const iy = Math.min(p.y + p.height, q.y + q.height) - Math.max(p.y, q.y);
        expect(ix > 1 && iy > 1, `${label}: buttons overlap in ${bar}`).toBe(false);
      }
    }
  }
}

test.describe.serial("design", () => {
  test.setTimeout(120_000);
  test.beforeAll(async ({ browser }) => {
    server = await startServer();
    page = await (await browser.newContext({ viewport: { width: 1280, height: 720 }, locale: "de-DE" })).newPage();
    page.on("dialog", (d) => { void d.accept(); });
    await page.goto(server.url);
    await expect(page.locator("button.tool").first()).toBeVisible({ timeout: 30_000 });
  });
  test.afterAll(() => { server.kill(); });

  test("start", async () => {
    await page.getByRole("button", { name: "Öffnen", exact: true }).click();
    await page.getByRole("dialog", { name: "Öffnen" }).getByRole("button", { name: /log_errors.*mitgeliefert/ }).click();
    await expect(page.locator(".react-flow__node")).toHaveCount(6);
    await expect(page.locator(".react-flow__node").first().locator(".react-flow__handle")).toHaveCount(4); // find: in, next, stdin, stdout
    await expect(page.locator(".react-flow__edge-text", { hasText: "stdout → stdin" })).toHaveCount(1);
    await page.getByText("Legende", { exact: true }).click();
    await noOverlap("start");
    await shot("start");
    await page.getByText("Legende", { exact: true }).click();
  });

  test("form", async () => {
    await page.locator(".react-flow__node", { hasText: "zaehle" }).click();
    await expect(page.locator(".step-panel")).toBeVisible();
    await expect(page.getByTestId("cmd-display")).toBeVisible({ timeout: 10_000 });
    await noOverlap("form");
    await shot("form");
  });

  test("help", async () => {
    await page.getByRole("button", { name: "Wie Daten fließen" }).click();
    await expect(page.getByRole("dialog", { name: "Wie Daten fließen" })).toContainText("{{ schritt.stdout }}");
    await shot("help");
    await page.keyboard.press("Escape");
  });

  test("blocks", async () => {
    await page.getByRole("button", { name: "Blöcke", exact: true }).click();
    await expect(page.locator("#blk-zaehle")).toContainText("Eingabe: stdout von suche");
    await noOverlap("blocks");
    await shot("blocks");
    await page.getByRole("button", { name: "Graph", exact: true }).click();
  });

  test("run panel", async () => {
    await page.getByRole("button", { name: "Trockenlauf" }).click();
    await expect(page.getByTestId("plan")).toContainText("grep");
    await noOverlap("run");
    await shot("run");
  });

  test("large font", async () => {
    await page.getByRole("button", { name: "Einstellungen" }).click();
    await page.getByLabel("Schriftgröße").selectOption("large");
    await page.locator("dialog[open]").getByRole("button", { name: "Schließen" }).click();
    await noOverlap("large font");
    await shot("large");
    await page.getByRole("button", { name: "Einstellungen" }).click();
    await page.getByLabel("Schriftgröße").selectOption("normal");
    await page.locator("dialog[open]").getByRole("button", { name: "Schließen" }).click();
  });

  test("dark mode", async () => {
    const toggle = page.getByTestId("theme-toggle");
    const html = page.locator("html");
    await page.emulateMedia({ colorScheme: "dark" }); // theme "system" follows the OS
    await expect(html).toHaveAttribute("data-theme", "dark");
    await page.emulateMedia({ colorScheme: "light" });
    await expect(html).toHaveAttribute("data-theme", "light");
    while ((await toggle.getAttribute("data-theme")) !== "dark") await toggle.click(); // system -> light -> dark
    await expect(html).toHaveAttribute("data-theme", "dark");
    await noOverlap("dark");
    await shot("dark");
    await page.goto(server.url); // reload would lose the one-time token
    await expect(toggle).toHaveAttribute("data-theme", "dark");
    await expect(html).toHaveAttribute("data-theme", "dark");
    await toggle.click(); // dark -> system
    await expect(toggle).toHaveAttribute("data-theme", "system");
  });

  test("run view", async () => {
    await page.getByRole("button", { name: "Modus Ausführen" }).click();
    await page.getByRole("region", { name: "Bibliothek" }).getByRole("button", { name: /log_errors/ }).click();
    await expect(page.getByRole("region", { name: "Eingaben" }).getByLabel("Log-Ordner")).toBeVisible();
    await page.getByRole("region", { name: "Eingaben" }).getByRole("button", { name: "Trockenlauf" }).click();
    await expect(page.getByTestId("runview-plan")).toContainText("grep");
    await noOverlap("run view", 2);
    await shot("runview");
    await page.getByRole("button", { name: "Erstellen", exact: true }).click();
  });
});
