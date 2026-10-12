// SPDX-License-Identifier: AGPL-3.0-or-later
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e-results",
  workers: 1,
  reporter: "list",
  use: { viewport: { width: 1400, height: 900 }, locale: "de-DE", screenshot: "only-on-failure", trace: "off" },
});
