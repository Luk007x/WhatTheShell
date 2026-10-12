// SPDX-License-Identifier: AGPL-3.0-or-later
// Response types of docs/API.md. Spec types are reused from the generated module schema types.
import type { Example, InputSpec, OptionSpec, Safety } from "./module";
import type { Workflow } from "./workflow";

export type { Example, InputSpec, OptionSpec, Safety, Workflow };

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

export interface WorkflowListItem {
  id: string;
  name: string;
  path: string;
  source: "bundled" | "user";
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
  variables: Record<string, unknown>;
  cwd: string | null;
  dry_run: boolean;
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
