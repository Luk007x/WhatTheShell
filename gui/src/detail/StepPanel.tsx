// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useRef, useState } from "react";
import { ApiError, errMsg, getTool, postCommand, postPreview } from "../api";
import { useDebounced } from "../hooks";
import { t } from "../i18n";
import {
  argsFromForm, conditionOperator, conditionWith, fieldKind, firstSentence, linesOf, matchesQuery,
  OPERATORS, rawFromArg, sortOptions, type OperatorName, type RawValue, type Spec,
} from "../model/form";
import { isCommand, visibleSteps, type Step } from "../model/ops";
import type { CommandResult, OptionSpec, PreviewResult, SandboxStatus, ToolInfo } from "../types/api";
import type { CommandStep, Workflow } from "../types/workflow";

export type Update = (patch: Record<string, unknown>, key?: string) => void;

const msg = errMsg;
const ON_ERROR = ["abort", "continue", "retry", "fallback"] as const;
const toolCache = new Map<string, Promise<ToolInfo>>();
function loadTool(tool: string, sub: string[]): Promise<ToolInfo> {
  const key = `${tool}\u0000${sub.join("/")}`;
  let p = toolCache.get(key);
  if (!p) {
    p = getTool(tool, { sub });
    toolCache.set(key, p);
    p.catch(() => toolCache.delete(key)); // do not cache failures
  }
  return p;
}

/** One-value-per-line textarea; keeps its own draft so trailing newlines survive. */
function LinesArea({ id, value, onChange }: { id: string; value: string[]; onChange: (v: string[]) => void }) {
  const [draft, setDraft] = useState(value.join("\n"));
  return <textarea id={id} rows={3} value={draft} onChange={(e) => { setDraft(e.target.value); onChange(linesOf(e.target.value)); }} />;
}

function Field({ idPrefix, spec, value, onChange }: { idPrefix: string; spec: Spec; value: unknown; onChange: (raw: RawValue) => void }) {
  const kind = fieldKind(spec, value);
  const raw = rawFromArg(spec, value);
  const id = `${idPrefix}-${spec.id}`;
  const flags = "flags" in spec ? (spec.flags ?? []) : [];
  const short = firstSentence(spec.help);
  const str = typeof raw === "string" ? raw : "";
  const hasTemplate = typeof value === "string" && value.includes("{{");
  let control;
  if (kind === "checkbox") control = <input id={id} type="checkbox" checked={raw === true} onChange={(e) => onChange(e.target.checked)} />;
  else if (kind === "textarea") control = <LinesArea id={id} value={Array.isArray(raw) ? raw : []} onChange={onChange} />;
  else if (kind === "tuple") {
    const n = "nargs" in spec ? (spec.nargs ?? 2) : 2;
    const vals = Array.isArray(raw) ? raw : [];
    control = (
      <span className="tuple">
        {Array.from({ length: n }, (_, i) => (
          <input key={i} aria-label={`${spec.label ?? flags.join(", ")} ${i + 1}`} value={vals[i] ?? ""}
            onChange={(e) => onChange(Array.from({ length: n }, (_, j) => (j === i ? e.target.value : (vals[j] ?? ""))))} />
        ))}
      </span>
    );
  } else if (kind === "select") {
    const choices = spec.choices ?? [];
    control = (
      <select id={id} value={str} onChange={(e) => onChange(e.target.value)}>
        <option value="" />
        {str && !choices.includes(str) && <option value={str}>{str}</option>}
        {choices.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
    );
  } else {
    control = (
      <input id={id} type={kind === "number" ? "number" : kind === "password" ? "password" : "text"} value={str}
        step={spec.type === "float" ? "any" : undefined} min={spec.min ?? undefined} max={spec.max ?? undefined}
        placeholder={kind === "path" ? t("field.path.placeholder") : (spec.metavar ?? undefined)}
        onChange={(e) => onChange(e.target.value)} />
    );
  }
  return (
    <div className="field">
      <label htmlFor={id} title={spec.help ?? undefined}>
        {spec.label ?? flags.join(", ")}
        {spec.required && <span aria-label={t("field.required")} className="req"> *</span>}
        {flags.length > 0 && spec.label && <small className="flags"> {flags.join(", ")}</small>}
        {spec.confidence && spec.confidence !== "high" && (
          <span className="badge" title={t("field.guessed.title")}> {t("field.guessed")}</span>
        )}
      </label>
      {control}
      {hasTemplate && <small className="muted">{t("field.template")}</small>}
      {short && <small className="muted help">{short}</small>}
      {spec.help && spec.help.trim() !== short && (
        <details><summary>{t("field.more")}</summary><p>{spec.help}</p></details>
      )}
    </div>
  );
}

function CommandForm({ step, wf, sandbox, onRetest, update }: {
  step: CommandStep; wf: Workflow; sandbox: SandboxStatus | null; onRetest: () => void; update: Update;
}) {
  const sub = step.command ?? [];
  const [root, setRoot] = useState<ToolInfo | null>(null);
  const [info, setInfo] = useState<ToolInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const subKey = sub.join("/");

  useEffect(() => {
    let stale = false;
    setError(null);
    const run = async () => {
      const r = await loadTool(step.tool, []);
      const i = sub.length > 0 ? await loadTool(step.tool, sub) : r;
      if (!stale) { setRoot(r); setInfo(i); }
    };
    run().catch((e: unknown) => { if (!stale) setError(msg(e)); });
    return () => { stale = true; };
  }, [step.tool, subKey]); // eslint-disable-line -- `sub` is derived from subKey

  const args = step.args ?? {};
  const setField = (spec: Spec) => (raw: RawValue) => update({ args: argsFromForm(args, spec, raw) }, `args.${spec.id}`);
  const spec = info?.command;
  const sorted = spec ? sortOptions(spec.options, query) : null;
  const subs = root?.command.subcommands ?? [];
  const prefix = `f-${step.id}`;
  const renderOption = (o: OptionSpec) => <Field key={o.id} idPrefix={prefix} spec={o} value={args[o.id]} onChange={setField(o)} />;

  return (
    <>
      {error && <p role="alert" className="error">{t("error.network", { message: error })}</p>}
      {subs.length > 0 && (
        <div className="field">
          <label htmlFor={`${prefix}-sub`}>{t("step.sub")}</label>
          <select id={`${prefix}-sub`} value={subKey} onChange={(e) => update({ command: e.target.value ? e.target.value.split("/") : undefined })}>
            <option value="" />
            {subs.map((s) => <option key={s.name.join("/")} value={s.name.slice(1).join("/") || s.name.join("/")}>{s.name.join(" ")}</option>)}
          </select>
        </div>
      )}
      {spec && sorted && (
        <>
          {spec.summary && <p>{spec.summary}</p>}
          {spec.inputs.length > 0 && <h4>{t("step.inputs")}</h4>}
          {[...spec.inputs].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)).filter((i) => matchesQuery({ ...i, flags: [] } as OptionSpec, query)).map((i) => (
            <Field key={i.id} idPrefix={prefix} spec={i} value={args[i.id]} onChange={setField(i)} />
          ))}
          <h4>{t("step.options")}</h4>
          <input type="search" aria-label={t("step.search")} placeholder={t("step.search")} value={query} onChange={(e) => setQuery(e.target.value)} />
          {sorted.groups.map((g) => (
            <fieldset key={g.name ?? ""}>
              <legend>{g.name ?? t("catalog.other")}</legend>
              {g.options.map(renderOption)}
            </fieldset>
          ))}
          {sorted.rare.length > 0 && (
            <details open={query !== ""}>
              <summary>{t("step.rare")} ({sorted.rare.length})</summary>
              {sorted.rare.map(renderOption)}
            </details>
          )}
        </>
      )}
      <div className="field">
        <label htmlFor={`${prefix}-extra`}>{t("step.extra")}</label>
        <LinesArea id={`${prefix}-extra`} value={step.extra_args ?? []} onChange={(v) => update({ extra_args: v.filter(Boolean).length ? v.filter(Boolean) : undefined }, "extra_args")} />
        <small className="muted">{t("step.extra.help")}</small>
      </div>
      <StdinAndErrors step={step} wf={wf} update={update} />
      <CommandView step={step} />
      <Preview step={step} info={info} sandbox={sandbox} onRetest={onRetest} update={update} />
    </>
  );
}

function StdinAndErrors({ step, wf, update }: { step: CommandStep; wf: Workflow; update: Update }) {
  const p = `f-${step.id}`;
  const stdin = step.stdin ?? {};
  const mode = stdin.pipe !== undefined ? "pipe" : stdin.text !== undefined ? "text" : stdin.file !== undefined ? "file" : "none";
  const before = visibleSteps(wf, step.id);
  const setMode = (m: string) =>
    update({ stdin: m === "pipe" ? { pipe: before[before.length - 1] ?? "" } : m === "text" ? { text: "" } : m === "file" ? { file: "" } : undefined });
  const action = step.on_error?.action ?? "abort";
  const [okText, setOkText] = useState((step.ok_exit_codes ?? [0]).join(", "));
  const okCodes = okText.split(",").map((x) => x.trim()).filter(Boolean).map(Number);
  const okValid = okCodes.every(Number.isInteger);
  // rebuilt per action so no leftovers (retries, steps) survive a switch
  const setOnError = (a: string, retries?: number) => {
    const next = ON_ERROR.find((x) => x === a);
    update({
      on_error:
        next === undefined || next === "abort" ? undefined
        : next === "retry" ? { action: next, ...(retries !== undefined ? { retries } : {}) }
        : next === "fallback" ? { action: next, steps: step.on_error?.steps ?? [] }
        : { action: next },
    });
  };
  return (
    <>
      <div className="field">
        <label htmlFor={`${p}-stdin`}>{t("step.stdin")}</label>
        <select id={`${p}-stdin`} value={mode} onChange={(e) => setMode(e.target.value)}>
          {["none", "pipe", "text", "file"].map((m) => <option key={m} value={m}>{t(`stdin.${m}`)}</option>)}
        </select>
        {mode === "pipe" && (
          <select aria-label={t("stdin.pipe")} value={stdin.pipe ?? ""} onChange={(e) => update({ stdin: { pipe: e.target.value } })}>
            <option value="" />
            {before.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        )}
        {mode === "text" && <textarea aria-label={t("stdin.text")} rows={3} value={stdin.text ?? ""} onChange={(e) => update({ stdin: { text: e.target.value } }, "stdin")} />}
        {mode === "file" && <input aria-label={t("stdin.file")} value={stdin.file ?? ""} placeholder={t("field.path.placeholder")} onChange={(e) => update({ stdin: { file: e.target.value } }, "stdin")} />}
      </div>
      <div className="field">
        <label htmlFor={`${p}-cwd`}>{t("step.cwd")}</label>
        <input id={`${p}-cwd`} value={step.cwd ?? ""} placeholder={t("field.path.placeholder")} onChange={(e) => update({ cwd: e.target.value || undefined }, "cwd")} />
      </div>
      <div className="field">
        <label htmlFor={`${p}-ok`}>{t("step.okcodes")}</label>
        <input id={`${p}-ok`} value={okText} aria-invalid={!okValid}
          onChange={(e) => {
            setOkText(e.target.value);
            const codes = e.target.value.split(",").map((x) => x.trim()).filter(Boolean).map(Number);
            if (codes.every(Number.isInteger)) update({ ok_exit_codes: codes.length > 0 && codes.join() !== "0" ? codes : undefined }, "ok");
          }} />
      </div>
      <div className="field">
        <label htmlFor={`${p}-timeout`}>{t("step.timeout")}</label>
        <input id={`${p}-timeout`} type="number" min={0} value={step.timeout ?? ""} onChange={(e) => update({ timeout: e.target.value === "" ? undefined : Number(e.target.value) }, "timeout")} />
      </div>
      <div className="field">
        <label htmlFor={`${p}-err`}>{t("step.onerror")}</label>
        <select id={`${p}-err`} value={action} onChange={(e) => setOnError(e.target.value)}>
          {ON_ERROR.map((a) => <option key={a} value={a}>{t(`onerror.${a}`)}</option>)}
        </select>
        {action === "retry" && (
          <input type="number" min={1} aria-label={t("onerror.retries")} value={step.on_error?.retries ?? ""} onChange={(e) => setOnError("retry", e.target.value === "" ? undefined : Number(e.target.value))} />
        )}
      </div>
    </>
  );
}

/** F-10: the resulting command as text, with copy button and safety class. */
function CommandView({ step }: { step: CommandStep }) {
  const req = useDebounced(JSON.stringify({ tool: step.tool, command: step.command ?? [], args: step.args ?? {}, extra_args: step.extra_args ?? [] }), 300);
  const [res, setRes] = useState<CommandResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    let stale = false;
    postCommand(JSON.parse(req) as Parameters<typeof postCommand>[0]) // own JSON.stringify above
      .then((r) => { if (!stale) { setRes(r); setErr(null); } })
      .catch((e: unknown) => { if (!stale) { setRes(null); setErr(msg(e)); } });
    return () => { stale = true; };
  }, [req]);
  const stdin = step.stdin;
  const suffix = stdin?.pipe ? ` < pipe: ${stdin.pipe}` : stdin?.text !== undefined ? " < text" : stdin?.file ? ` < datei: ${stdin.file}` : "";
  const copy = () => res && navigator.clipboard.writeText(res.display + suffix).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }, (e: unknown) => setErr(msg(e)));
  return (
    <section aria-label={t("cmd.title")}>
      <h4>{t("cmd.title")}</h4>
      {err && <p role="alert" className="error">{err}</p>}
      {res && (
        <>
          <code className="cmd" data-testid="cmd-display">{res.display + suffix}</code>{" "}
          <button onClick={copy}>{copied ? t("cmd.copied") : t("cmd.copy")}</button>
          <p>
            <span className={`dot ${res.safety}`} aria-hidden="true" />
            {t("cmd.safety")}: <strong>{t(`safety.${res.safety}`)}</strong>
          </p>
          {res.reasons.length > 0 && <ul>{res.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
        </>
      )}
    </section>
  );
}

/** F-12 to F-15: sandbox preview with example data. */
function Preview({ step, info, sandbox, onRetest, update }: { step: CommandStep; info: ToolInfo | null; sandbox: SandboxStatus | null; onRetest: () => void; update: Update }) {
  const examples = info?.command.examples ?? [];
  const [example, setExample] = useState<number | null>(null);
  const [applied, setApplied] = useState(false);
  const [res, setRes] = useState<PreviewResult | null>(null);
  const [err, setErr] = useState<ApiError | Error | null>(null);
  const [safety, setSafety] = useState<string | null>(null);
  const body = JSON.stringify({ tool: step.tool, command: step.command ?? [], args: step.args ?? {}, extra_args: step.extra_args ?? [], example, stdin: step.stdin?.text ?? null });
  const debounced = useDebounced(body, 600);

  const seq = useRef(0); // only the latest preview request may set state
  const run = (payload: string) => {
    const mine = ++seq.current;
    postPreview(JSON.parse(payload) as Parameters<typeof postPreview>[0]) // own JSON.stringify above
      .then((r) => { if (mine === seq.current) { setRes(r); setErr(null); } })
      .catch((e: unknown) => { if (mine === seq.current) setErr(e instanceof Error ? e : new Error(String(e))); });
  };
  useEffect(() => {
    let stale = false;
    postCommand(JSON.parse(debounced) as Parameters<typeof postCommand>[0]).then((r) => { if (!stale) setSafety(r.safety); }, () => { if (!stale) setSafety(null); });
    return () => { stale = true; };
  }, [debounced]);
  const auto = sandbox?.available === true && safety === "safe" && example !== null;
  useEffect(() => { if (auto) run(debounced); }, [debounced, auto]); // eslint-disable-line -- run is stable in effect

  const unavailable = sandbox?.available === false || (err instanceof ApiError && err.status === 409);
  return (
    <section aria-label={t("prev.title")}>
      <h4>{t("prev.title")}</h4>
      <label>
        {t("prev.example")}{" "}
        <select value={example ?? ""} onChange={(e) => {
          const i = e.target.value === "" ? null : Number(e.target.value);
          setExample(i);
          const args = i === null ? undefined : examples[i]?.args;
          if (args) { update({ args: { ...args } }); setApplied(true); } else setApplied(false);
        }}>
          <option value="">{t("prev.none")}</option>
          {examples.map((x, i) => <option key={i} value={i}>{x.title}</option>)}
        </select>
      </label>{" "}
      {applied && <small className="muted">{t("prev.applied")} </small>}
      <button disabled={sandbox?.available === false} onClick={() => run(body)}>{t("prev.run")}</button>
      {unavailable && (
        <p role="alert" className="error">
          {t("prev.sandbox")}: {sandbox?.reason} {sandbox?.install_hint} <button onClick={onRetest}>{t("prev.retest")}</button>
        </p>
      )}
      {err && !unavailable && <p role="alert" className="error">{err.message}</p>}
      {res && (
        <div className="preview">
          <code className="cmd">{res.command}</code>
          {res.stdout && <pre className="stdout" aria-label={t("stream.stdout")}>{res.stdout}</pre>}
          {res.stderr && <pre className="stderr" aria-label={t("stream.stderr")}><strong>{t("stream.stderr")}: </strong>{res.stderr}</pre>}
          <p>
            {t("prev.exit")}: <strong>{res.exit_code}</strong> · {t("prev.duration")}: {res.duration.toFixed(2)} s
            {res.truncated && ` · ${t("prev.truncated")}`}{res.timed_out && ` · ${t("prev.timeout")}`}
          </p>
        </div>
      )}
    </section>
  );
}

function Text({ id, label, value, onChange, type = "text", list }: { id: string; label: string; value: string | number; onChange: (v: string) => void; type?: string; list?: string }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type={type} value={value} list={list} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function ControlForm({ step, wf, update }: { step: Exclude<Step, CommandStep>; wf: Workflow; update: Update }) {
  const p = `f-${step.id}`;
  const before = visibleSteps(wf, step.id);
  const sources = [
    ...before.flatMap((b) => ["stdout", "stderr", "exit_code"].map((k) => `${b}.${k}`)),
    ...Object.keys(wf.variables ?? {}).map((v) => `var.${v}`),
    "item",
  ];
  const list = (
    <datalist id={`${p}-src`}>{sources.map((s) => <option key={s} value={s} />)}</datalist>
  );
  switch (step.kind) {
    case "if": {
      const op = conditionOperator(step.condition) ?? "eq";
      const spec = OPERATORS.find(([k]) => k === op);
      const raw = step.condition[op as OperatorName];
      return (
        <>
          {list}
          <Text id={`${p}-src-i`} label={t("cond.source")} list={`${p}-src`} value={step.condition.source} onChange={(v) => update({ condition: { ...step.condition, source: v } }, "source")} />
          <div className="field">
            <label htmlFor={`${p}-op`}>{t("cond.operator")}</label>
            <select id={`${p}-op`} value={op} onChange={(e) => update({ condition: conditionWith(step.condition, e.target.value as OperatorName, spec?.[1] === "bool" ? true : "") })}>
              {/* cast: option values come from OPERATORS */}
              {OPERATORS.map(([k]) => <option key={k} value={k}>{t(`op.${k}`)}</option>)}
            </select>
          </div>
          {spec?.[1] === "bool" ? (
            <label><input type="checkbox" checked={raw === true} onChange={(e) => update({ condition: conditionWith(step.condition, op, e.target.checked) })} /> {t("cond.true")}</label>
          ) : (
            <Text id={`${p}-val`} label={t("cond.value")} type={spec?.[1] === "number" ? "number" : "text"} value={raw === undefined || raw === null ? "" : String(raw)} onChange={(v) => update({ condition: conditionWith(step.condition, op, v) }, "value")} />
          )}
        </>
      );
    }
    case "foreach":
      return (
        <>
          {list}
          <Text id={`${p}-src-i`} label={t("cond.source")} list={`${p}-src`} value={step.source} onChange={(v) => update({ source: v }, "source")} />
          <Text id={`${p}-as`} label={t("foreach.as")} value={step.as ?? ""} onChange={(v) => update({ as: v || undefined }, "as")} />
        </>
      );
    case "set":
      return (
        <>
          <div className="field">
            <label htmlFor={`${p}-var`}>{t("set.variable")}</label>
            <select id={`${p}-var`} value={step.variable} onChange={(e) => update({ variable: e.target.value })}>
              <option value="" />
              {Object.keys(wf.variables ?? {}).map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <Text id={`${p}-val`} label={t("set.value")} value={step.value} onChange={(v) => update({ value: v }, "value")} />
        </>
      );
    case "wait":
      return <Text id={`${p}-sec`} type="number" label={t("wait.seconds")} value={step.seconds} onChange={(v) => update({ seconds: Number(v) }, "seconds")} />;
    case "message":
      return <Text id={`${p}-text`} label={t("message.text")} value={step.text} onChange={(v) => update({ text: v }, "text")} />;
    case "abort":
      return (
        <>
          <Text id={`${p}-text`} label={t("message.text")} value={step.text ?? ""} onChange={(v) => update({ text: v || undefined }, "text")} />
          <Text id={`${p}-exit`} type="number" label={t("abort.exit")} value={step.exit_code ?? 1} onChange={(v) => update({ exit_code: Number(v) }, "exit")} />
        </>
      );
  }
}

export function StepPanel(props: {
  step: Step; wf: Workflow; sandbox: SandboxStatus | null; onRetest: () => void;
  update: Update; rename: (newId: string) => void; remove: () => void;
}) {
  const { step } = props;
  const [idDraft, setIdDraft] = useState(step.id);
  return (
    <div className="step-panel">
      <h3>{step.label ?? step.id}</h3>
      <Text id={`f-${step.id}-id`} label={t("step.id")} value={idDraft} onChange={(v) => { setIdDraft(v); }} />
      {idDraft !== step.id && <button onClick={() => props.rename(idDraft)}>{t("step.rename")}</button>}
      <Text id={`f-${step.id}-label`} label={t("step.label")} value={step.label ?? ""} onChange={(v) => props.update({ label: v || undefined }, "label")} />
      {isCommand(step) ? (
        <CommandForm step={step} wf={props.wf} sandbox={props.sandbox} onRetest={props.onRetest} update={props.update} />
      ) : (
        <ControlForm step={step} wf={props.wf} update={props.update} />
      )}
      <p><button onClick={props.remove}>{t("canvas.delete")}</button></p>
    </div>
  );
}
