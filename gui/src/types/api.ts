// SPDX-License-Identifier: AGPL-3.0-or-later
// Response types of docs/API.md. Spec types are reused from the generated module schema types.
import type { Example, InputSpec, OptionSpec, Safety } from "./module";
import type { VariableSpec, Workflow } from "./workflow";

export type { Example, InputSpec, OptionSpec, Safety, VariableSpec, Workflow };

// Mirrors models/catalog.py CommandSpec (not part of the JSON schemas).
export interface CommandSpec {
  name: string[];
  summary?: string | null;
  usage?: string | null;
  inputs: InputSpec[];
  options: OptionSpec[];
  subcommands: CommandSpec[];
  raw_help?: string | null;
  confidence: "high" | "medium" | "low";
  safety: Safety;
  interactive: boolean;
  display_name?: string | null;
  category?: string | null;
  description?: string | null;
  examples: Example[];
}

// Mirrors models/catalog.py ToolInfo.
export interface ToolInfo {
  name: string;
  path: string;
  version?: string | null;
  source: "module" | "help" | "man" | "fallback";
  module_files: string[];
  command: CommandSpec;
}

export interface ToolSummary {
  name: string;
  path: string;
  display_name?: string | null;
  category?: string | null;
  summary?: string | null;
  safety?: Safety | null;
  /** Interactive tool (same source as `ToolInfo.command.interactive`). */
  interactive?: boolean;
}

export interface SandboxStatus {
  available: boolean;
  reason: string;
  install_hint: string;
  bwrap_path: string | null;
}

export interface Status {
  app: string;
  version: string;
  sandbox: SandboxStatus;
  module_errors: { path: string; line: number | null; message: string }[];
  config_dir: string;
  workflows_dir: string;
}

export interface CommandRequest {
  tool: string;
  command: string[];
  args: Record<string, unknown>;
  extra_args: string[];
}

export interface CommandResult {
  argv: string[];
  display: string;
  safety: Safety;
  reasons: string[];
}

export interface PreviewRequest extends CommandRequest {
  example: number | null;
  stdin: string | null;
}

export interface PreviewResult {
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration: number;
  truncated: boolean;
  timed_out: boolean;
}

export type WorkflowSource = "bundled" | "user" | "project";

/** Library index entry of `GET /api/workflows`. */
export interface WorkflowListItem {
  id: string;
  name: string;
  description: string | null;
  source: WorkflowSource;
  path: string;
  variables: Record<string, VariableSpec>;
  steps: number;
  error: string | null;
  shadows: WorkflowSource[];
  /** false when a project file wins: PUT/DELETE answer 409 `shadowed`. */
  writable: boolean;
}

export interface WorkflowDoc {
  id: string;
  path: string;
  document: Workflow;
  raw: string;
}

export interface ValidationResult {
  ok: boolean;
  errors: { path: string; message: string }[];
}

export interface RunRequest {
  document: Workflow;
  variables: Record<string, string>;
  cwd: string | null;
  dry_run: boolean;
  /** keep the terminal output (never keystrokes) as a file; default false */
  transcript?: boolean;
}

/** Body of `POST /api/workflows/{id}/run`: the document comes from the library index. */
export type WorkflowRunRequest = Omit<RunRequest, "document">;

/** Entry of `GET /api/runs` (newest first). */
export interface RunListItem {
  run_id: string;
  status: "created" | "running" | "success" | "failed" | "aborted";
  workflow_name: string;
  started: string | null;
  finished: string | null;
  exit_code: number | null;
}

export interface RunCreated {
  run_id: string;
  plan: string;
  needs_confirmation: boolean;
  max_safety: Safety;
  cwd?: string;
}

export type RunEvent = { type: string; [key: string]: unknown };

export interface RunState {
  status: string;
  events: RunEvent[];
}

export type RunAction = "abort" | "pause" | "resume" | "step";

// Mirrors whattheshell.settings.Settings (docs/API.md "Einstellungen"); `key_status` is read-only, sent by GET only.
export interface Settings {
  schema_version: number;
  ai: {
    enabled: boolean;
    provider: "local" | "api" | "agent";
    local: { base_url: string; model: string; timeout: number };
    api: { kind: "anthropic" | "openai"; base_url: string | null; model: string; key_env: string; key_source: "env" | "keyring"; timeout: number };
    agent: { kind: "claude" | "codex"; model: string; reasoning: "" | "low" | "medium" | "high"; timeout: number };
    send_outputs: boolean;
  };
  key_status?: "set" | "missing";
  /** Read-only, sent by GET only: settings.yaml could not be read. */
  load_error?: string | null;
}

/** Per agent program: absolute path (null = not on PATH), known models, program default, reasoning support (GET /api/ai/agents). */
export interface AiAgentInfo { path: string | null; models: string[]; default: string; reasoning: boolean }
export type AiAgents = Record<"claude" | "codex", AiAgentInfo>;

export type AiTaskName = "improve-module" | "examples" | "draft-workflow" | "diagnose";
export type AiBody =
  | { tool: string }
  | { description: string; name?: string }
  | { step: Record<string, unknown>; include_output: boolean };
export interface AiPreview { prompt: { system: string; user: string }; chars: number }
export interface AiResult {
  kind: "module" | "workflow" | "text";
  raw: string;
  errors: string[];
  diff: string;
  target: string | null;
  valid: boolean;
}
