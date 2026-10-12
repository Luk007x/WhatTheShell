// SPDX-License-Identifier: AGPL-3.0-or-later
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type ProxyOptions } from "vite";

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
    plugins: [react()],
    build: { outDir: "../src/whattheshell/api/static", emptyOutDir: true },
    server: { proxy: { "/api": proxy, "/ws": { ...proxy, ws: true } } },
  };
});
