// SPDX-License-Identifier: AGPL-3.0-or-later
// Embedded terminal of a terminal step (docs/SECURITY.md 7.3/7.4): xterm.js on a binary WebSocket.
// Nothing the program prints may reach the browser outside the terminal: no clipboard (OSC 52), no title (OSC 0/1/2),
// no hyperlinks (OSC 8, no link addon), no image addons. Keystrokes only go to the socket and are stored nowhere.
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef, useState } from "react";
import { deleteTranscript, errMsg, wsUrl } from "../api";
import { t } from "../i18n";
import type { TerminalEnd as End, TerminalState } from "../model/run";

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const theme = () => ({ background: css("--surface"), foreground: css("--text"), cursor: css("--accent"), selectionBackground: css("--accent-weak"), selectionForeground: css("--text") });

/** Close codes with their own message; any other abnormal close gets the generic one. */
const KNOWN_CLOSE = new Set([4404, 4408, 4409, 4413, 4429]);

export function TerminalPane({ runId, terminal, transcript, onClose }: {
  runId: string | null; terminal: TerminalState; transcript: boolean; onClose: (code: number | null) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const el = host.current;
    if (!el || !runId) return;
    const term = new Terminal({ theme: theme(), fontFamily: "ui-monospace, Menlo, Consolas, monospace", fontSize: 14, cursorBlink: true });
    const fit = new FitAddon();
    term.loadAddon(fit);
    // Programs and displayed files are untrusted: swallow clipboard, title and hyperlink sequences.
    for (const osc of [0, 1, 2, 8, 52]) term.parser.registerOscHandler(osc, () => true);
    // Tab belongs to the program; Esc followed by Tab hands the focus back to the page (keyboard escape).
    let esc = false;
    term.attachCustomKeyEventHandler((e) => {
      if (e.type !== "keydown") return true;
      if (e.key === "Tab" && esc) { esc = false; e.preventDefault(); wrap.current?.focus(); return false; }
      esc = e.key === "Escape";
      return true;
    });
    term.open(el);
    fit.fit();
    term.focus();

    // Opened in a timer so React StrictMode's mount/cleanup/mount in dev never has two sockets (4409) for one terminal.
    let sock: WebSocket | null = null;
    const send = (o: object) => { if (sock?.readyState === WebSocket.OPEN) sock.send(JSON.stringify(o)); };
    const enc = new TextEncoder();
    term.onData((d) => { if (sock?.readyState === WebSocket.OPEN) sock.send(enc.encode(d)); }); // never stored
    const timer = setTimeout(() => {
      const s = new WebSocket(wsUrl(`/ws/runs/${encodeURIComponent(runId)}/terminal/${encodeURIComponent(terminal.stepId)}`));
      sock = s;
      s.binaryType = "arraybuffer";
      s.onopen = () => { fit.fit(); send({ type: "open", cols: term.cols, rows: term.rows }); };
      s.onmessage = (m) => {
        if (m.data instanceof ArrayBuffer) { term.write(new Uint8Array(m.data)); return; }
        try { // text frames are control messages; only {type:"error"} is shown, as text
          const f: unknown = JSON.parse(String(m.data));
          if (f && typeof f === "object" && "type" in f && f.type === "error" && "message" in f && typeof f.message === "string") setServerError(f.message);
        } catch { /* not JSON: ignore */ }
      };
      s.onclose = (ev) => { if (ev.code !== 1000 && ev.code !== 1005) onCloseRef.current(ev.code); }; // 1000: reported by terminal_closed
    }, 0);
    const ro = new ResizeObserver(() => { fit.fit(); send({ type: "resize", cols: term.cols, rows: term.rows }); });
    ro.observe(el);
    const themes = new MutationObserver(() => { term.options.theme = theme(); });
    themes.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { ro.disconnect(); themes.disconnect(); clearTimeout(timer); if (sock) { sock.onclose = null; sock.close(); } term.dispose(); }; // closing ends the process (7.3)
  }, [runId, terminal.stepId]);

  return (
    <section className="terminal" ref={wrap} tabIndex={-1} aria-label={t("term.region")}>
      <p className="hint">{t("term.hint")}{(terminal.transcript ?? transcript) && <> <span className="badge badge--caution" role="status">{t("term.recording")}</span></>}</p>
      {serverError !== null && <p role="status" className="error">{t("term.server_error", { message: serverError })}</p>}
      <div className="terminal__host" ref={host} role="group" aria-label={t("term.label", { command: terminal.command })} />
    </section>
  );
}

/** After the terminal ended: exit code, transcript notice with delete button, or the reason of an abnormal close. */
export function TerminalEnd({ end, closeCode }: { end: End | null; closeCode: number | null }) {
  const [gone, setGone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const name = end?.transcript ?? null;
  return (
    <>
      {closeCode !== null && <p role="alert" className="error">{KNOWN_CLOSE.has(closeCode) ? t(`term.close.${closeCode}`) : t("term.close.other", { code: closeCode })}</p>}
      {end && (
        <div className="terminal-end" role="status">
          <p>{t("term.ended", { code: end.exitCode ?? "-" })}</p>
          {name !== null && gone !== name && (
            <p>
              {t("term.saved")} <code>{name}</code>{" "}
              <button className="btn--sm" onClick={() => { deleteTranscript(name).then(() => setGone(name), (e: unknown) => setError(errMsg(e))); }}>{t("term.delete")}</button>
            </p>
          )}
          {gone !== null && gone === name && <p>{t("term.deleted")}</p>}
          {error !== null && <p role="alert" className="error">{error}</p>}
        </div>
      )}
    </>
  );
}
