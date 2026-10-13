// SPDX-License-Identifier: AGPL-3.0-or-later
// One field per workflow variable plus the working directory; used by the run view and the editor's run dialog.
import { t } from "../i18n";
import type { VariableSpec } from "../types/api";
import { patternOf, type FieldError, type FormValues } from "./runForm";

export function RunForm({ prefix, variables, values, errors = {}, cwd, onValues, onCwd, transcript, onTranscript }: {
  /** id prefix, unique per page */
  prefix: string;
  variables: Record<string, VariableSpec>;
  values: FormValues;
  errors?: Record<string, FieldError>;
  cwd: string;
  onValues: (values: FormValues) => void;
  onCwd: (cwd: string) => void;
  /** undefined: the workflow has no terminal step, the option is not shown */
  transcript?: boolean;
  onTranscript?: (on: boolean) => void;
}) {
  const set = (name: string, v: string | boolean) => onValues({ ...values, [name]: v });
  return (
    <>
      {Object.entries(variables).map(([name, v]) => {
        const id = `${prefix}-${name}`;
        const value = values[name];
        const err = errors[name];
        const pattern = v.type === "string" ? patternOf(v) : undefined;
        const help = [v.help, v.type === "path" ? t("runform.path") : null, pattern ? t("runform.pattern", { pattern }) : null].filter(Boolean).join(" ");
        const describedBy = [help && `${id}-help`, err && `${id}-err`].filter(Boolean).join(" ") || undefined;
        const label = <>{v.label ?? name}{v.required && <span className="req" aria-hidden="true"> *</span>}</>;
        if (v.type === "bool") {
          return (
            <div className="field" key={name}>
              <label><input type="checkbox" checked={value === true} aria-describedby={describedBy} onChange={(e) => set(name, e.target.checked)} /> {label}</label>
              {help && <small className="muted" id={`${id}-help`}>{help}</small>}
            </div>
          );
        }
        const common = {
          id, "aria-invalid": err !== undefined, "aria-describedby": describedBy, required: v.required,
        };
        const text = typeof value === "string" ? value : "";
        const choices = v.type === "enum" ? v.choices ?? [] : [];
        const numeric = v.type === "int" || v.type === "float";
        const control = choices.length > 0 ? (
          <select {...common} value={text} onChange={(e) => set(name, e.target.value)}>
            {(!v.required || !choices.includes(text)) && <option value="">{t("runform.choose")}</option>}
            {choices.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        ) : (
          <input {...common} type={numeric ? "number" : v.type === "secret" ? "password" : "text"} step={v.type === "float" ? "any" : undefined} pattern={pattern} title={pattern ? t("runform.pattern", { pattern }) : undefined}
            min={numeric ? v.min ?? undefined : undefined} max={numeric ? v.max ?? undefined : undefined} value={text}
            autoComplete={v.type === "secret" ? "off" : undefined} onChange={(e) => set(name, e.target.value)} />
        );
        const range = numeric && (v.min != null || v.max != null) ? t("runform.range", { min: v.min ?? "–", max: v.max ?? "–" }) : null;
        return (
          <div className="field" key={name}>
            <label htmlFor={id}>{label} <small className="muted">{name}{range ? ` · ${range}` : ""}</small></label>
            {control}
            {help && <small className="muted" id={`${id}-help`}>{help}</small>}
            {err && <small className="error" id={`${id}-err`}>{t(`runform.err.${err}`, { min: v.min ?? "", max: v.max ?? "", pattern: pattern ?? "" })}</small>}
          </div>
        );
      })}
      <div className="field">
        <label htmlFor={`${prefix}-cwd`}>{t("step.cwd")}</label>
        <input id={`${prefix}-cwd`} value={cwd} placeholder={t("run.cwd.placeholder")} onChange={(e) => onCwd(e.target.value)} />
      </div>
      {transcript !== undefined && (
        <div className="field">
          <label><input type="checkbox" checked={transcript} onChange={(e) => onTranscript?.(e.target.checked)} /> {t("run.transcript")}</label>
        </div>
      )}
    </>
  );
}
