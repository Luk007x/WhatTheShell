// SPDX-License-Identifier: AGPL-3.0-or-later
import { createContext, Fragment, useContext } from "react";
import { t } from "./i18n";
import { Icon } from "./icons";
import { Modal } from "./Modal";

/** Help sections with their number of paragraphs (p) and bullets (b); texts live in i18n as `help.<section>.p1..`/`.b1..`. */
const SECTIONS = {
  start: { p: 0, b: 6 },
  build: { p: 0, b: 5 },
  run: { p: 0, b: 6 },
  modules: { p: 0, b: 4 },
  terminal: { p: 0, b: 5 },
  ai: { p: 0, b: 6 },
  keys: { p: 0, b: 0 },
} as const;
export type HelpSection = keyof typeof SECTIONS;
export const HELP_SECTIONS = Object.keys(SECTIONS) as HelpSection[];

/** `openHelp(section)` from App; the default does nothing (components rendered outside of the app). */
export const HelpContext = createContext<(section: HelpSection) => void>(() => undefined);

/** Small "?" button for a panel header: opens Help at `section`. `topic` is the already translated panel name. */
export function HelpButton({ section, topic }: { section: HelpSection; topic: string }) {
  const openHelp = useContext(HelpContext);
  const label = t("help.about", { topic });
  return <button className="btn--icon" aria-label={label} title={label} onClick={() => openHelp(section)}><Icon name="help" /></button>;
}

/** Backticks in the text mark code. */
const rich = (text: string) => text.split("`").map((part, i) => (i % 2 ? <code key={i}>{part}</code> : <Fragment key={i}>{part}</Fragment>));
const range = (n: number) => Array.from({ length: n }, (_, i) => i + 1);

function Content({ section }: { section: HelpSection }) {
  const { p, b } = SECTIONS[section];
  return (
    <div className="help-content" role="tabpanel" id="help-panel" aria-labelledby={`help-tab-${section}`}>
      <h3>{t(`help.${section}.title`)}</h3>
      {range(p).map((i) => <p key={i} className="help-text">{rich(t(`help.${section}.p${i}`))}</p>)}
      {b > 0 && <ul className="help-text">{range(b).map((i) => <li key={i}>{rich(t(`help.${section}.b${i}`))}</li>)}</ul>}
      {section === "keys" && (
        <>
          <table>
            <thead><tr><th scope="col">{t("keys.col.key")}</th><th scope="col">{t("keys.col.do")}</th></tr></thead>
            <tbody>
              {(["delete", "undo", "redo", "save", "esc", "enter", "help"] as const).map((r) => (
                <tr key={r}><td><kbd>{t(`keys.${r}.key`)}</kbd></td><td>{t(`keys.${r}.do`)}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="muted">{t("keys.drag")}</p>
        </>
      )}
    </div>
  );
}

/** Help dialog: section list on the left, content on the right (stacked on narrow screens). `section` null = closed. */
export function Help({ section, onSection, onClose }: { section: HelpSection | null; onSection: (s: HelpSection) => void; onClose: () => void }) {
  return (
    <Modal open={section !== null} title={t("help.title")} onCancel={onClose}>
      {section !== null && (
        <>
          <div className="help">
            <div role="tablist" aria-orientation="vertical" aria-label={t("help.sections")} className="help-tabs">
              {HELP_SECTIONS.map((s) => (
                <button key={s} role="tab" id={`help-tab-${s}`} aria-selected={s === section} aria-controls="help-panel" tabIndex={s === section ? 0 : -1}
                  onClick={() => onSection(s)}
                  onKeyDown={(e) => {
                    const d = e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 0;
                    if (d === 0) return;
                    e.preventDefault();
                    const next = HELP_SECTIONS[(HELP_SECTIONS.indexOf(s) + d + HELP_SECTIONS.length) % HELP_SECTIONS.length];
                    if (next) { onSection(next); requestAnimationFrame(() => document.getElementById(`help-tab-${next}`)?.focus()); }
                  }}>
                  {t(`help.${s}.title`)}
                </button>
              ))}
            </div>
            <Content section={section} />
          </div>
          <div className="actions"><button data-autofocus onClick={onClose}>{t("settings.close")}</button></div>
        </>
      )}
    </Modal>
  );
}
