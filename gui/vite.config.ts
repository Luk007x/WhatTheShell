// SPDX-License-Identifier: AGPL-3.0-or-later
import react from "@vitejs/plugin-react";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Marked } from "marked";
import { defineConfig, loadEnv, type Plugin, type ProxyOptions } from "vite";
import { slug, type ManualChapter, type ManualHeading } from "./src/manual/manualData";

const MANUAL_DIR = resolve(__dirname, "../docs/manual");
const plain = (md: string) => md.replace(/[`*_]|\[([^\]]*)\]\([^)]*\)/g, "$1");

/** `docs/manual/NN-slug.md` → chapters (HTML, search text, headings) as the virtual module `virtual:manual`. Content is ours, not user input. */
function manualPlugin(): Plugin {
  const id = "virtual:manual";
  return {
    name: "wts-manual",
    resolveId: (source) => (source === id ? `\0${id}` : undefined),
    load(resolved) {
      if (resolved !== `\0${id}`) return undefined;
      const files = existsSync(MANUAL_DIR) ? readdirSync(MANUAL_DIR).filter((f) => /^\d+-.+\.md$/.test(f)).sort() : [];
      this.addWatchFile(MANUAL_DIR);
      const chapters: ManualChapter[] = files.map((f) => {
        const path = resolve(MANUAL_DIR, f);
        this.addWatchFile(path);
        const headings: ManualHeading[] = [];
        let title = "";
        const marked = new Marked({
          renderer: {
            heading({ text, depth, tokens }) {
              const inner = this.parser.parseInline(tokens);
              if (depth === 1) { title ||= plain(text); return `<h1 tabindex="-1">${inner}</h1>\n`; }
              if (depth > 3) return `<h${depth}>${inner}</h${depth}>\n`;
              const hid = slug(plain(text));
              headings.push({ id: hid, text: plain(text), level: depth as 2 | 3 }); // depth is 2 or 3 after the guards above
              return `<h${depth} id="${hid}">${inner}</h${depth}>\n`;
            },
          },
        });
        const html = marked.parse(readFileSync(path, "utf8"), { async: false });
        // ponytail: tag strip for search text only, entities stay encoded; fine for German substring search of plain words
        const text = html.replace(/<[^>]+>/g, " ").replace(/&(amp|lt|gt|quot|#39);/g, (_, e: string) => ({ amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" })[e] ?? "").replace(/\s+/g, " ").trim();
        return { id: f.replace(/^\d+-/, "").replace(/\.md$/, ""), title: title || f, html, text, headings };
      });
      return `export const chapters = ${JSON.stringify(chapters)};`;
    },
  };
}

export default defineConfig(({ mode }) => {
  const port = loadEnv(mode, process.cwd(), "VITE_").VITE_WTS_PORT ?? "8000";
  const target = `http://127.0.0.1:${port}`;
  // The backend only accepts Origin 127.0.0.1/localhost with its own port: rewrite it.
  const proxy: ProxyOptions = {
    target,
    changeOrigin: false,
    configure: (p) => {
      p.on("proxyReq", (r) => r.setHeader("Origin", target));
      p.on("proxyReqWs", (r) => r.setHeader("Origin", target));
    },
  };
  return {
    base: "./",
    plugins: [react(), manualPlugin()],
    build: { outDir: "../src/whattheshell/api/static", emptyOutDir: true },
    server: { proxy: { "/api": proxy, "/ws": { ...proxy, ws: true } } },
  };
});
