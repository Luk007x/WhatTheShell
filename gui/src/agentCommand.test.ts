// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { agentCommand } from "./Settings";

describe("agentCommand", () => {
  it("claude without model has no --model", () => expect(agentCommand("claude", "", "")).not.toContain("--model"));
  it("claude with model", () => expect(agentCommand("claude", "X", "")).toEqual([
    "claude", "-p", "--output-format", "text", "--tools", "", "--permission-mode", "dontAsk", "--no-session-persistence",
    "--system-prompt", "{system}", "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands", "--model", "X"]));
  it("codex with model and reasoning", () => expect(agentCommand("codex", "X", "high")).toEqual([
    "codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--color", "never",
    "-c", "mcp_servers={}", "-C", "{tmp}", "-o", "{tmp}/last.txt", "-m", "X", "-c", 'model_reasoning_effort="high"', "-"]));
});
