// SPDX-License-Identifier: AGPL-3.0-or-later
// Pure reduction of run events (WebSocket / history) into a displayable state.
import type { RunEvent } from "../types/api";

export interface StepBlock {
  key: number;
  id: string;
  command: string;
  safety: string;
  lines: { stream: "stdout" | "stderr"; text: string }[];
  finish?: { ok: boolean; exit_code: number | null; duration: number | null; attempt: number | null };
  skipped?: string;
  messages: string[];
  /** terminal step: the output lives in the terminal, not in `lines` */
  interactive?: boolean;
}
export interface ConfirmRequest { step_id: string; command: string; safety: string; reasons: string[] }
export interface TerminalState { stepId: string; command: string; /** set by the server; absent in older histories */ transcript?: boolean }
export interface TerminalEnd { stepId: string; exitCode: number | null; transcript: string | null }
export type RunStatus = "idle" | "running" | "success" | "failed" | "aborted";
export interface RunView {
  status: RunStatus;
  blocks: StepBlock[];
  confirm: ConfirmRequest | null;
  message: string | null;
  exitCode: number | null;
  /** the last terminal step: live between terminal_request and terminal_closed, afterwards kept as read-only view until the next one replaces it */
  terminal: TerminalState | null;
  terminalEnd: TerminalEnd | null;
}

export const initialRun: RunView = { status: "idle", blocks: [], confirm: null, message: null, exitCode: null, terminal: null, terminalEnd: null };

const str = (e: RunEvent, k: string): string => (typeof e[k] === "string" ? e[k] : "");
const num = (e: RunEvent, k: string): number | null => (typeof e[k] === "number" ? e[k] : null);

function patchLast(blocks: StepBlock[], id: string, fn: (b: StepBlock) => StepBlock): StepBlock[] {
  let i = blocks.length - 1;
  while (i >= 0 && blocks[i]?.id !== id) i--;
  const block = blocks[i];
  if (!block) return [...blocks, fn({ key: blocks.length, id, command: "", safety: "safe", lines: [], messages: [] })];
  return blocks.map((b, j) => (j === i ? fn(b) : b));
}

export function reduceEvents(s: RunView, e: RunEvent): RunView {
  const id = str(e, "step_id");
  const running: RunView = s.status === "idle" ? { ...s, status: "running" } : s;
  switch (e.type) {
    case "step_started":
      return {
        ...running,
        confirm: null,
        blocks: [...running.blocks, { key: running.blocks.length, id, command: str(e, "command"), safety: str(e, "safety") || "safe", lines: [], messages: [] }],
      };
    case "output": {
      const stream = e.stream === "stderr" ? "stderr" : "stdout";
      return { ...running, blocks: patchLast(running.blocks, id, (b) => ({ ...b, lines: [...b.lines, { stream, text: str(e, "text") }] })) };
    }
    case "step_finished":
      return {
        ...running,
        confirm: running.confirm?.step_id === id ? null : running.confirm,
        blocks: patchLast(running.blocks, id, (b) => ({ ...b, finish: { ok: e.ok === true, exit_code: num(e, "exit_code"), duration: num(e, "duration"), attempt: num(e, "attempt") } })),
      };
    case "step_skipped":
      return { ...running, blocks: patchLast(running.blocks, id, (b) => ({ ...b, skipped: str(e, "reason") || "-" })) };
    case "message":
      return { ...running, blocks: patchLast(running.blocks, id, (b) => ({ ...b, messages: [...b.messages, str(e, "text")] })) };
    case "confirm_request": {
      const reasons = Array.isArray(e.reasons) ? e.reasons.filter((r): r is string => typeof r === "string") : [];
      return { ...running, confirm: { step_id: id, command: str(e, "command"), safety: str(e, "safety") || "caution", reasons } };
    }
    case "terminal_request":
      return {
        ...running, terminal: { stepId: id, command: str(e, "command"), ...(typeof e.transcript === "boolean" ? { transcript: e.transcript } : {}) }, terminalEnd: null,
        blocks: patchLast(running.blocks, id, (b) => ({ ...b, interactive: true })),
      };
    case "terminal_closed":
      return { ...running, terminalEnd: { stepId: id, exitCode: num(e, "exit_code"), transcript: str(e, "transcript") || null } };
    case "finished": {
      const status = e.status === "success" || e.status === "aborted" ? e.status : "failed";
      return { ...running, status, confirm: null, message: str(e, "message") || null, exitCode: num(e, "exit_code") };
    }
    default:
      return s;
  }
}
