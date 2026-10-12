// SPDX-License-Identifier: AGPL-3.0-or-later
import type {
  CommandRequest, CommandResult, PreviewRequest, PreviewResult, RunAction, RunCreated, RunRequest,
  RunState, SandboxStatus, Status, ToolInfo, ToolSummary, ValidationResult, Workflow, WorkflowDoc, WorkflowListItem,
} from "./types/api";

export const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

export class ApiError extends Error {
  constructor(public status: number, public error: string, message: string, public errors: { path: string; message: string }[] = []) {
    super(message);
    this.name = "ApiError";
  }
}

/** Extract the token from a location hash such as `#token=abc`. */
export function parseToken(hash: string): string | null {
  return new URLSearchParams(hash.replace(/^#/, "")).get("token") || null;
}

let token: string | null = null;

/** Read the token from the URL fragment once and remove the fragment from the address bar. */
export function initToken(): string | null {
  const found = parseToken(location.hash);
  if (found) {
    token = found;
    history.replaceState(null, "", location.pathname + location.search);
  }
  return token;
}

export const hasToken = (): boolean => token !== null;

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "X-WTS-Token": token ?? "" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T; // no body, callers declare void
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    if (res.ok) throw new ApiError(res.status, "body", `HTTP ${res.status}: ungültige JSON-Antwort`);
  }
  if (!res.ok) {
    const e = (data ?? {}) as { error?: string; message?: string; errors?: { path: string; message: string }[] };
    throw new ApiError(res.status, e.error ?? "http", e.message ?? `HTTP ${res.status}`, Array.isArray(e.errors) ? e.errors : []);
  }
  if (data === null && res.status !== 202) throw new ApiError(res.status, "body", `HTTP ${res.status}: leere Antwort`);
  return data as T; // the server contract in docs/API.md is the trust boundary
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  del: <T>(path: string) => request<T>("DELETE", path),
};

export function wsUrl(path: string): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}${path}?token=${encodeURIComponent(token ?? "")}`;
}

const enc = encodeURIComponent;

export const getStatus = () => api.get<Status>("/api/status");
export const listTools = (search = "") => api.get<ToolSummary[]>(`/api/tools?search=${enc(search)}`);
export const getTool = (name: string, opts: { sub?: string[]; deep?: boolean; refresh?: boolean } = {}) =>
  api.get<ToolInfo>(
    `/api/tools/${enc(name)}?sub=${enc((opts.sub ?? []).join("/"))}&deep=${opts.deep ? 1 : 0}&refresh=${opts.refresh ? 1 : 0}`,
  );
export const postCommand = (req: CommandRequest) => api.post<CommandResult>("/api/command", req);
export const postPreview = (req: PreviewRequest) => api.post<PreviewResult>("/api/preview", req);
export const listWorkflows = () => api.get<WorkflowListItem[]>("/api/workflows");
export const getWorkflow = (id: string) => api.get<WorkflowDoc>(`/api/workflows/${enc(id)}`);
export const putWorkflow = (id: string, document: Workflow) =>
  api.put<{ id: string; path: string }>(`/api/workflows/${enc(id)}`, { document });
export const deleteWorkflow = (id: string) => api.del<void>(`/api/workflows/${enc(id)}`);
export const validateWorkflow = (document: Workflow) =>
  api.post<ValidationResult>("/api/workflows/validate", { document });
export const createRun = (req: RunRequest) => api.post<RunCreated>("/api/runs", req);
export const startRun = (id: string) => api.post<void>(`/api/runs/${enc(id)}/start`);
export const getRun = (id: string) => api.get<RunState>(`/api/runs/${enc(id)}`);
export const controlRun = (id: string, action: RunAction) =>
  api.post<void>(`/api/runs/${enc(id)}/control`, { action });
export const confirmRun = (id: string, stepId: string, ok: boolean) =>
  api.post<void>(`/api/runs/${enc(id)}/confirm`, { step_id: stepId, ok });
export const postSelftest = () => api.post<SandboxStatus>("/api/sandbox/selftest");
