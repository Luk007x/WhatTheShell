// SPDX-License-Identifier: AGPL-3.0-or-later
import { t } from "../i18n";
import { ID_PATTERN } from "../model/ops";
import type { Workflow } from "../types/workflow";

type Vars = NonNullable<Workflow["variables"]>;
const TYPES = ["string", "int", "float", "bool", "path", "enum", "secret"] as const;

export function VariablesPanel({ variables, onChange }: { variables: Workflow["variables"]; onChange: (v: Vars) => void }) {
  const vars: Vars = variables ?? {};
  const setVar = (name: string, patch: Vars[string]) => onChange({ ...vars, [name]: { ...vars[name], ...patch } });
  const rename = (old: string, next: string) => {
    if (next === old || !ID_PATTERN.test(next) || next in vars) return;
    onChange(Object.fromEntries(Object.entries(vars).map(([k, v]) => [k === old ? next : k, v])));
  };
  const remove = (name: string) => onChange(Object.fromEntries(Object.entries(vars).filter(([k]) => k !== name)));
  const add = () => {
    let n = 1;
    while (`var${n}` in vars) n++;
    onChange({ ...vars, [`var${n}`]: { type: "string" } });
  };
  return (
    <section aria-label={t("vars.title")}>
      <h3>{t("vars.title")}</h3>
      <table>
        <thead>
          <tr><th>{t("vars.name")}</th><th>{t("vars.type")}</th><th>{t("vars.default")}</th><th>{t("vars.label")}</th><th /></tr>
        </thead>
        <tbody>
          {Object.entries(vars).map(([name, v]) => (
            <tr key={name}>
              <td><input aria-label={t("vars.name")} defaultValue={name} onBlur={(e) => rename(name, e.target.value)} /></td>
              <td>
                <select aria-label={t("vars.type")} value={v.type ?? "string"} onChange={(e) => setVar(name, { type: e.target.value as (typeof TYPES)[number] })}>
                  {TYPES.map((x) => <option key={x}>{x}</option>)}
                </select>
              </td>
              <td><input aria-label={t("vars.default")} value={v.default === undefined || v.default === null ? "" : String(v.default)}
                onChange={(e) => setVar(name, { default: e.target.value === "" ? undefined : v.type === "int" || v.type === "float" ? Number(e.target.value) : e.target.value })} /></td>
              <td><input aria-label={t("vars.label")} value={v.label ?? ""} onChange={(e) => setVar(name, { label: e.target.value || undefined })} /></td>
              <td><button aria-label={`${t("vars.remove")} ${name}`} onClick={() => remove(name)}>×</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={add}>{t("vars.add")}</button>
    </section>
  );
}
