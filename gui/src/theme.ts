// SPDX-License-Identifier: AGPL-3.0-or-later
// Appearance: "system" follows the OS; the resolved value lands in <html data-theme> (CSS reads only that).
export type Theme = "system" | "light" | "dark";
const KEY = "wts.theme";
const QUERY = "(prefers-color-scheme: dark)";

export const THEMES: readonly Theme[] = ["system", "light", "dark"];

export function getTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch { return "system"; }
}

export function setTheme(t: Theme): void {
  try { localStorage.setItem(KEY, t); } catch { /* storage unavailable: the choice lasts for this session */ }
}

let stop: (() => void) | null = null;

export function applyTheme(t: Theme): void {
  stop?.();
  stop = null;
  const root = document.documentElement;
  if (t !== "system") { root.dataset.theme = t; return; }
  const mq = window.matchMedia(QUERY);
  const set = () => { root.dataset.theme = mq.matches ? "dark" : "light"; };
  set();
  mq.addEventListener("change", set);
  stop = () => mq.removeEventListener("change", set);
}
