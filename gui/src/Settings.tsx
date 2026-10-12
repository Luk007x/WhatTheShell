// SPDX-License-Identifier: AGPL-3.0-or-later
import { getLang, t, type Lang } from "./i18n";
import { Modal } from "./Modal";

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
export const applyFontSize = (size: FontSize): void => { document.documentElement.style.setProperty("--font-scale", String(SCALE[size])); };
export const saveFontSize = (size: FontSize): void => write("wts.fontsize", size);

export function Settings(props: {
  open: boolean; onClose: () => void;
  lang: Lang; onLang: (l: Lang) => void;
  fontSize: FontSize; onFontSize: (s: FontSize) => void;
  autoPreview: boolean; onAutoPreview: (on: boolean) => void;
}) {
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
        <label><input type="checkbox" checked={props.autoPreview} onChange={(e) => props.onAutoPreview(e.target.checked)} /> {t("settings.autopreview")}</label>
      </div>
      <div className="actions"><button onClick={props.onClose}>{t("settings.close")}</button></div>
    </Modal>
  );
}
