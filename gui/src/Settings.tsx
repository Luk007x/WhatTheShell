// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState, type ReactNode } from "react";
import { ApiError, errMsg, getAiAgents, getSettings, postShutdown, putSettings } from "./api";
import { HelpButton } from "./Help";
import { getLang, t, type Lang } from "./i18n";
import { Modal } from "./Modal";
import type { AiAgents, Settings as ServerSettings } from "./types/api";

export type FontSize = "small" | "normal" | "large";
const SCALE: Record<FontSize, number> = { small: 0.875, normal: 1, large: 1.25 };

const read = (key: string): string | null => {
  try { return localStorage.getItem(key); } catch { return null; }
};
const write = (key: string, value: string): void => {
  try { localStorage.setItem(key, value); } catch { /* storage unavailable: the choice lasts for this session */ }
};

export const loadFontSize = (): FontSize => {
  const v = read("wts.fontsize");
  return v === "small" || v === "large" ? v : "normal";
};
export const loadAutoPreview = (): boolean => read("wts.autopreview") !== "off";
export const saveAutoPreview = (on: boolean): void => write("wts.autopreview", on ? "on" : "off");

export const START_VIEWS = ["last", "build-graph", "build-blocks", "run", "modules"] as const;
export type StartView = (typeof START_VIEWS)[number];
export const loadHelpStart = (): boolean => read("wts.helpstart") !== "off";
export const saveHelpStart = (on: boolean): void => write("wts.helpstart", on ? "on" : "off");
/** Open the help on first start only when it was not seen yet and the setting is on. */
export const shouldOpenHelp = (seen: boolean, enabled: boolean): boolean => !seen && enabled;
export const loadStartView = (): StartView => START_VIEWS.find((v) => v === read("wts.startview")) ?? "last";
export const saveStartView = (v: StartView): void => write("wts.startview", v);
/** Mode and view at app start: a fixed start view wins over the last-used mode/view. */
export function initialModeView<M extends string, V extends string>(startView: StartView, savedMode: M, savedView: V, modes: { build: M; run: M; modules: M }, views: { graph: V; blocks: V }): { mode: M; view: V } {
  switch (startView) {
    case "build-graph": return { mode: modes.build, view: views.graph };
    case "build-blocks": return { mode: modes.build, view: views.blocks };
    case "run": return { mode: modes.run, view: savedView };
    case "modules": return { mode: modes.modules, view: savedView };
    case "last": return { mode: savedMode, view: savedView };
  }
}
export const applyFontSize = (size: FontSize): void => { document.documentElement.style.setProperty("--font-scale", String(SCALE[size])); };
export const saveFontSize = (size: FontSize): void => write("wts.fontsize", size);

const REASONING = ["", "low", "medium", "high"] as const;
export const MODEL_PATTERN = "[A-Za-z0-9][A-Za-z0-9._:\\-]{0,63}";

/** Effective argv of the agent call, mirrors the server defaults (src/whattheshell/ai/providers/agent_cli.py). */
export function agentCommand(kind: "claude" | "codex", model: string, reasoning: string): string[] {
  if (kind === "claude") {
    return ["claude", "-p", "--output-format", "text", "--tools", "", "--permission-mode", "dontAsk", "--no-session-persistence",
      "--system-prompt", "{system}", "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands", ...(model ? ["--model", model] : [])];
  }
  return ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--color", "never",
    "-c", "mcp_servers={}", "-C", "{tmp}", "-o", "{tmp}/last.txt", ...(model ? ["-m", model] : []),
    ...(reasoning ? ["-c", `model_reasoning_effort="${reasoning}"`] : []), "-"];
}
const quoteArg = (a: string): string => (/^[\w@%+=:,./{}-]+$/.test(a) ? a : `"${a}"`);

/** "KI-Funktionen (optional)": edits only known fields, everything else of the server document is sent back unchanged. */
function AiSettings({ onChanged }: { onChanged: (enabled: boolean) => void }) {
  const [doc, setDoc] = useState<ServerSettings | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [overwrite, setOverwrite] = useState(false);
  const [agents, setAgents] = useState<AiAgents | null>(null);
  const [otherModel, setOtherModel] = useState(false);
  const [agentsError, setAgentsError] = useState<unknown>(null);
  const agentMode = doc?.ai.enabled === true && doc.ai.provider === "agent";
  useEffect(() => { getSettings().then(setDoc, setError); }, []);
  useEffect(() => {
    if (!agentMode || agents) return;
    let live = true;
    setAgentsError(null);
    getAiAgents().then((r) => { if (live) setAgents(r); }, (e: unknown) => { if (live) setAgentsError(e); });
    return () => { live = false; };
  }, [agentMode, agents]);
  if (!doc) return <section><h3>{t("ai.settings")}</h3>{error !== null && <p role="alert" className="error">{errMsg(error)}</p>}</section>;
  const ai = doc.ai;
  const edit = (patch: Partial<ServerSettings["ai"]>) => { setSaved(false); setDoc({ ...doc, ai: { ...ai, ...patch } }); };
  const text = (id: string, label: string, value: string, set: (v: string) => void, help?: string) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} value={value} aria-describedby={help ? `${id}-h` : undefined} onChange={(e) => set(e.target.value)} />
      {help && <small className="muted" id={`${id}-h`}>{help}</small>}
    </div>
  );
  const choice = <K extends string>(id: string, label: string, value: K, values: readonly K[], set: (v: K) => void, show: (v: K) => string = (v) => v, help?: ReactNode) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} aria-describedby={help ? `${id}-h` : undefined} onChange={(e) => { const v = values.find((x) => x === e.target.value); if (v) set(v); }}>
        {values.map((v) => <option key={v} value={v}>{show(v)}</option>)}
      </select>
      {help && <div id={`${id}-h`}>{help}</div>}
    </div>
  );
  const save = () => {
    setError(null);
    putSettings(doc).then((r) => { setDoc(r); setSaved(true); setOverwrite(false); onChanged(r.ai.enabled); }, (e: unknown) => { setSaved(false); setError(e); });
  };
  const { local, api, agent } = ai;
  return (
    <section aria-labelledby="ai-set-h">
      <div className="hhead"><h3 id="ai-set-h">{t("ai.settings")}</h3><HelpButton section="ai" topic={t("ai.settings")} /></div>
      {doc.load_error && <p role="alert" className="error">{doc.load_error} {t("ai.loaderror.hint")}</p>}
      <div className="field">
        <label><input type="checkbox" checked={ai.enabled} onChange={(e) => edit({ enabled: e.target.checked })} /> {t("ai.enable")}</label>
        <small className="muted">{t("ai.enable.hint")}</small>
      </div>
      {ai.enabled && (
        <>
          {choice("ai-provider", t("ai.provider"), ai.provider, ["local", "api", "agent"], (provider) => edit({ provider }), (v) => t(`ai.provider.${v}`), <small className="muted">{t("ai.provider.help")}</small>)}
          {ai.provider === "local" && (
            <>
              {text("ai-l-url", t("ai.l.url"), local.base_url, (base_url) => edit({ local: { ...local, base_url } }), t("ai.l.url.help"))}
              {text("ai-l-model", t("ai.model"), local.model, (model) => edit({ local: { ...local, model } }), t("ai.model.local.help"))}
            </>
          )}
          {ai.provider === "api" && (
            <>
              {choice("ai-a-kind", t("ai.a.kind"), api.kind, ["anthropic", "openai"], (kind) => edit({ api: { ...api, kind } }), undefined, <small className="muted">{t("ai.a.kind.help")}</small>)}
              {text("ai-a-url", t("ai.a.url"), api.base_url ?? "", (v) => edit({ api: { ...api, base_url: v === "" ? null : v } }), t("ai.a.url.help"))}
              {text("ai-a-model", t("ai.model"), api.model, (model) => edit({ api: { ...api, model } }), t("ai.model.api.help"))}
              {text("ai-a-env", t("ai.keyenv"), api.key_env, (key_env) => edit({ api: { ...api, key_env } }), t("ai.keyenv.help"))}
              <p role="status">{t("ai.keystatus")}: <strong>{t(`ai.key.${doc.key_status ?? "missing"}`)}</strong></p>
              {choice("ai-a-src", t("ai.keysrc"), api.key_source, ["env", "keyring"], (key_source) => edit({ api: { ...api, key_source } }), (v) => t(`ai.keysrc.${v}`), <small className="muted">{t("ai.keysrc.help")}</small>)}
            </>
          )}
          {ai.provider === "agent" && (
            <>
              {choice("ai-g-kind", t("ai.g.kind"), agent.kind, ["claude", "codex"], (kind) => edit({ agent: { ...agent, kind } }),
                (k) => (agents ? `${k} – ${t(agents[k].path ? "ai.agent.found" : "ai.agent.missing")}` : k),
                <>
                  {agents && <small className="muted">{agents[agent.kind].path ?? t("ai.agent.hint")}</small>}
                  {agentsError !== null && <small role="alert" className="error">{errMsg(agentsError)}</small>}
                </>)}
              {(() => {
                const info = agents?.[agent.kind];
                const models = info?.models ?? [];
                const showText = models.length === 0 || otherModel || (agent.model !== "" && !models.includes(agent.model));
                const setAgent = (patch: Partial<typeof agent>) => edit({ agent: { ...agent, ...patch } });
                return (
                  <>
                    {models.length > 0 && (
                      <div className="field">
                        <label htmlFor="ai-g-model">{t("ai.g.model")}</label>
                        <select id="ai-g-model" value={showText ? "\u0000other" : agent.model}
                          onChange={(e) => { const other = e.target.value === "\u0000other"; setOtherModel(other); if (!other) setAgent({ model: e.target.value }); }}>
                          <option value="">{t("ai.g.model.default")}</option>
                          {models.map((m) => <option key={m} value={m}>{m}</option>)}
                          <option value="\u0000other">{t("ai.g.model.other")}</option>
                        </select>
                      </div>
                    )}
                    {showText && (
                      <div className="field">
                        <label htmlFor="ai-g-model-text">{models.length > 0 ? t("ai.g.model.other") : t("ai.g.model")}</label>
                        <input id="ai-g-model-text" pattern={MODEL_PATTERN} maxLength={64} value={agent.model} aria-describedby="ai-g-model-text-h" onChange={(e) => setAgent({ model: e.target.value })} />
                        <small className="muted" id="ai-g-model-text-h">{t("ai.g.model.help")}</small>
                      </div>
                    )}
                    {info?.reasoning && choice("ai-g-reasoning", t("ai.g.reasoning"), agent.reasoning, REASONING, (reasoning) => setAgent({ reasoning }), (v) => (v === "" ? t("ai.g.model.default") : v))}
                    <div className="field">
                      <span id="ai-g-cmd-l">{t("ai.g.call")}</span>{" "}
                      <code aria-labelledby="ai-g-cmd-l" aria-describedby="ai-g-cmd-h">{agentCommand(agent.kind, agent.model, agent.reasoning).map(quoteArg).join(" ")}</code>
                      <small className="muted" id="ai-g-cmd-h">{t("ai.g.call.help")} {t(`ai.g.call.${agent.kind}`)}</small>
                    </div>
                  </>
                );
              })()}
              <div className="field">
                <label htmlFor="ai-g-timeout">{t("ai.timeout")}</label>
                <input id="ai-g-timeout" type="number" min={1} value={agent.timeout} onChange={(e) => edit({ agent: { ...agent, timeout: Number(e.target.value) } })} />
              </div>
            </>
          )}
          <div className="field">
            <label><input type="checkbox" checked={ai.send_outputs} onChange={(e) => edit({ send_outputs: e.target.checked })} /> {t("ai.sendoutputs")}</label>
            <small className="muted">{t("ai.sendoutputs.help")}</small>
          </div>
        </>
      )}
      {error !== null && (
        <div role="alert" className="error">
          <p>{errMsg(error)}</p>
          {error instanceof ApiError && error.errors.length > 0 && <ul>{error.errors.map((e, i) => <li key={i}><code>{e.path}</code> {e.message}</li>)}</ul>}
        </div>
      )}
      {saved && <p role="status" className="hint">{t("mod.saved")}</p>}
      {doc.load_error && <div className="field"><label><input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} /> {t("ai.loaderror.overwrite")}</label></div>}
      <button className="btn--primary" disabled={!!doc.load_error && !overwrite} onClick={save}>{t("file.save")}</button>
    </section>
  );
}

/** "Programm": stops the server after confirmation; the caller replaces the app with the closing view. */
function QuitSection({ onStopped }: { onStopped: () => void }) {
  const [error, setError] = useState<unknown>(null);
  const quit = () => {
    if (!window.confirm(t("quit.confirm"))) return;
    setError(null);
    postShutdown().then(onStopped, setError);
  };
  return (
    <section aria-labelledby="quit-h">
      <h3 id="quit-h">{t("quit.title")}</h3>
      <p className="muted">{t("quit.help")}</p>
      {error !== null && <p role="alert" className="error">{errMsg(error)}</p>}
      <button className="btn--danger" onClick={quit}>{t("quit.button")}</button>
    </section>
  );
}

export function Settings(props: {
  open: boolean; onClose: () => void; onStopped: () => void; onAiChanged: (enabled: boolean) => void;
  lang: Lang; onLang: (l: Lang) => void;
  fontSize: FontSize; onFontSize: (s: FontSize) => void;
  autoPreview: boolean; onAutoPreview: (on: boolean) => void;
}) {
  const [startView, setStartView] = useState<StartView>(loadStartView);
  const [helpStart, setHelpStart] = useState(loadHelpStart);
  return (
    <Modal open={props.open} title={t("settings.title")} onCancel={props.onClose}>
      <div className="field">
        <label htmlFor="set-lang">{t("lang.label")}</label>
        <select id="set-lang" data-autofocus value={getLang()} onChange={(e) => props.onLang(e.target.value === "en" ? "en" : "de")}>
          <option value="de">Deutsch</option>
          <option value="en">English</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor="set-font">{t("settings.font")}</label>
        <select id="set-font" value={props.fontSize} onChange={(e) => props.onFontSize(e.target.value === "small" || e.target.value === "large" ? e.target.value : "normal")}>
          {(["small", "normal", "large"] as const).map((s) => <option key={s} value={s}>{t(`settings.font.${s}`)}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="set-startview">{t("settings.view")}</label>
        <select id="set-startview" value={startView} onChange={(e) => { const v = START_VIEWS.find((x) => x === e.target.value) ?? "last"; setStartView(v); saveStartView(v); }}>
          {START_VIEWS.map((v) => <option key={v} value={v}>{t(`settings.view.${v}`)}</option>)}
        </select>
        <small className="muted">{t("settings.view.help")}</small>
      </div>
      <div className="field">
        <label><input type="checkbox" checked={props.autoPreview} onChange={(e) => props.onAutoPreview(e.target.checked)} /> {t("settings.autopreview")}</label>
        <small className="muted">{t("settings.autopreview.help")}</small>
      </div>
      <div className="field">
        <label><input type="checkbox" checked={helpStart} onChange={(e) => { setHelpStart(e.target.checked); saveHelpStart(e.target.checked); }} /> {t("settings.helpstart")}</label>
        <small className="muted">{t("settings.helpstart.help")}</small>
      </div>
      {props.open && <AiSettings onChanged={props.onAiChanged} />}
      {props.open && <QuitSection onStopped={props.onStopped} />}
      <div className="actions"><button onClick={props.onClose}>{t("settings.close")}</button></div>
    </Modal>
  );
}
