// SPDX-License-Identifier: AGPL-3.0-or-later
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join, resolve } from "node:path";

/** Starts `wts gui` on a free port with a throwaway config dir; resolves with the token URL. */
export function startServer(): Promise<{ url: string; kill: () => void }> {
  const root = resolve(import.meta.dirname, "../..");
  // own config, runtime and cache dirs: the instance check (gui.json in XDG_RUNTIME_DIR) must not see other servers
  const dirs = ["wts-cfg-", "wts-run-", "wts-cache-"].map((p) => mkdtempSync(join(tmpdir(), p))); // mkdtemp creates mode 0700
  const [cfg, runtime, cache] = dirs;
  // a fresh XDG_CACHE_HOME would make uv rebuild its cache (timeout): keep the real uv cache
  const uvCache = process.env.UV_CACHE_DIR ?? join(process.env.XDG_CACHE_HOME ?? join(homedir(), ".cache"), "uv");
  const proc = spawn("env", ["-u", "VIRTUAL_ENV", "uv", "run", "wts", "gui", "--no-browser", "--port", "0"], {
    cwd: root,
    env: { ...process.env, XDG_CONFIG_HOME: cfg, XDG_RUNTIME_DIR: runtime, XDG_CACHE_HOME: cache, UV_CACHE_DIR: uvCache },
  });
  const kill = () => { proc.kill("SIGTERM"); };
  return new Promise((ok, fail) => {
    let out = "";
    const timer = setTimeout(() => { clearInterval(poll); kill(); fail(new Error(`no URL after 30 s, output: ${out}`)); }, 30_000);
    // the server prints the URL only on a TTY; otherwise it is in gui.json of its runtime dir
    const poll = setInterval(() => {
      try {
        const info: unknown = JSON.parse(readFileSync(join(runtime, "whattheshell", "gui.json"), "utf8"));
        if (info && typeof info === "object" && "url" in info && typeof info.url === "string") { clearTimeout(timer); clearInterval(poll); ok({ url: info.url, kill }); }
      } catch { /* not written yet */ }
    }, 100);
    proc.stdout.on("data", (d: Buffer) => { out += d.toString(); });
    proc.stderr.on("data", (d: Buffer) => { out += d.toString(); });
    proc.on("exit", (code, signal) => {
      clearTimeout(timer); clearInterval(poll);
      for (const d of dirs) rmSync(d, { recursive: true, force: true });
      fail(new Error(`server exited (code ${code}, signal ${signal}): ${out}`));
    });
  });
}
