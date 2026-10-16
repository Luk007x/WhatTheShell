// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { HelpButton } from "../Help";
import { t } from "../i18n";
import { Icon } from "../icons";
import { ID_PATTERN } from "../model/ops";
import { patternOf } from "../run/runForm";
import type { Workflow } from "../types/workflow";

type Vars = NonNullable<Workflow["variables"]>;
const TYPES = ["string", "int", "float", "bool", "path", "enum", "secret"] as const;

function PatternInput({ value, onChange }: { value: string; onChange: (p: string) => void }) {
  let bad = false;
  try { new RegExp(value, "v"); } catch { bad = true; }
  return (
    <>
      <input aria-label={t("vars.pattern")} value={value} aria-invalid={bad} onChange={(e) => onChange(e.target.value)} />
      {bad && <small className="error" role="alert">{t("vars.pattern.invalid")}</small>}
    </>
  );
}

/** "a, b,,c" -> ["a","b","c"]; undefined when empty (the field is then omitted). */
export function parseChoices(text: string): string[] | undefined {
  const list = text.split(",").map((x) => x.trim()).filter(Boolean);
  return list.length > 0 ? list : undefined;
}

/** Keeps its own draft so a typed trailing comma survives the parse. */
function ChoicesInput({ value, disabled, onChange }: { value: string[]; disabled: boolean; onChange: (c: string[] | undefined) => void }) {
  const [draft, setDraft] = useState(value.join(", "));
  return <input aria-label={t("vars.choices")} disabled={disabled} value={disabled ? "" : draft} onChange={(e) => { setDraft(e.target.value); onChange(parseChoices(e.target.value)); }} />;
}

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
      <div className="hhead"><h3>{t("vars.title")}</h3><HelpButton section="build" topic={t("vars.title")} /></div>
      <table className="table">
        <thead>
          <tr><th>{t("vars.name")}</th><th>{t("vars.type")}</th><th>{t("vars.default")}</th><th>{t("vars.label")}</th><th>{t("vars.pattern")}</th><th>{t("vars.required")}</th><th>{t("vars.help")}</th><th>{t("vars.choices")}</th><th><span className="sr-only">{t("vars.remove.col")}</span></th></tr>
        </thead>
        <tbody>
          {Object.entries(vars).map(([name, v]) => (
            <tr key={name}>
              <td><input aria-label={t("vars.name")} defaultValue={name} onBlur={(e) => rename(name, e.target.value)} /></td>
              <td>
                <select aria-label={t("vars.type")} value={v.type ?? "string"} onChange={(e) => setVar(name, { type: e.target.value as (typeof TYPES)[number], ...(e.target.value === "enum" ? {} : { choices: undefined }), ...(e.target.value === "string" || e.target.value === "path" ? {} : { pattern: undefined }) })}>
                  {TYPES.map((x) => <option key={x}>{x}</option>)}
                </select>
              </td>
              <td><input aria-label={t("vars.default")} value={v.default === undefined || v.default === null ? "" : String(v.default)}
                onChange={(e) => setVar(name, { default: e.target.value === "" ? undefined : v.type === "int" || v.type === "float" ? Number(e.target.value) : e.target.value })} /></td>
              <td><input aria-label={t("vars.label")} value={v.label ?? ""} onChange={(e) => setVar(name, { label: e.target.value || undefined })} /></td>
              <td>
                {(v.type === "string" || v.type === "path") && <PatternInput value={patternOf(v) ?? ""} onChange={(p) => setVar(name, { pattern: p || undefined })} />}
              </td>
              <td><input type="checkbox" aria-label={t("vars.required")} checked={v.required === true} onChange={(e) => setVar(name, { required: e.target.checked || undefined })} /></td>
              <td><input aria-label={t("vars.help")} value={v.help ?? ""} onChange={(e) => setVar(name, { help: e.target.value || undefined })} /></td>
              <td><ChoicesInput key={`${v.type}|${(v.choices ?? []).join(",")}`} disabled={v.type !== "enum"} value={v.choices ?? []} onChange={(c) => setVar(name, { choices: c })} /></td>
              <td><button className="btn--icon" aria-label={`${t("vars.remove")} ${name}`} title={`${t("vars.remove")} ${name}`} onClick={() => remove(name)}><Icon name="trash" /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {Object.keys(vars).length === 0 && <p className="muted">{t("vars.empty")}</p>}
      <button onClick={add}><Icon name="plus" />{t("vars.add")}</button>
      <p className="muted">{t("vars.hint")}</p>
    </section>
  );
}
