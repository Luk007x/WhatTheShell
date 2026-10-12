// SPDX-License-Identifier: AGPL-3.0-or-later
import { Component, type ReactNode } from "react";
import { errMsg } from "../api";
import { t } from "../i18n";

/** Keeps a crash inside the module editor from blanking the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode; onReset: () => void }, { error: unknown }> {
  override state: { error: unknown } = { error: null };
  static getDerivedStateFromError(error: unknown) { return { error: error ?? new Error("unknown") }; }
  override render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="error">
        <p>{t("mod.crash", { message: errMsg(this.state.error) })}</p>
        <button onClick={() => { this.setState({ error: null }); this.props.onReset(); }}>{t("mod.reset")}</button>
      </div>
    );
  }
}
