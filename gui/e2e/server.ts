// SPDX-License-Identifier: AGPL-3.0-or-later
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

/** Starts `wts gui` on a free port with a throwaway config dir; resolves with the token URL. */
export function startServer(): Promise<{ url: string; kill: () => void }> {
  const root = resolve(import.meta.dirname, "../..");
  const proc = spawn("env", ["-u", "VIRTUAL_ENV", "uv", "run", "wts", "gui", "--no-browser", "--port", "0"], {
    cwd: root,
    env: { ...process.env, XDG_CONFIG_HOME: mkdtempSync(join(tmpdir(), "wts-cfg-")) },
  });
  const kill = () => { proc.kill("SIGTERM"); };
  return new Promise((ok, fail) => {
    let out = "";
    const timer = setTimeout(() => { kill(); fail(new Error(`no URL after 30 s, output: ${out}`)); }, 30_000);
    proc.stdout.on("data", (d: Buffer) => {
      out += d.toString();
      const m = /http:\/\/127\.0\.0\.1:\d+\/#token=\S+/.exec(out);
      if (m) { clearTimeout(timer); ok({ url: m[0], kill }); }
    });
    proc.stderr.on("data", (d: Buffer) => { out += d.toString(); });
    proc.on("exit", (c) => { clearTimeout(timer); fail(new Error(`server exited ${c}: ${out}`)); });
  });
}
