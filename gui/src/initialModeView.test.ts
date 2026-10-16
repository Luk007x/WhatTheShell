// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { initialModeView } from "./Settings";

const modes = { build: "build", run: "run", modules: "modules" } as const;
const views = { graph: "graph", blocks: "blocks" } as const;

describe("initialModeView", () => {
  it("last keeps the saved mode and view", () => {
    expect(initialModeView("last", "run", "blocks", modes, views)).toEqual({ mode: "run", view: "blocks" });
  });
  it("fixed start views override the saved state", () => {
    expect(initialModeView("build-graph", "run", "blocks", modes, views)).toEqual({ mode: "build", view: "graph" });
    expect(initialModeView("build-blocks", "run", "graph", modes, views)).toEqual({ mode: "build", view: "blocks" });
    expect(initialModeView("run", "build", "blocks", modes, views)).toEqual({ mode: "run", view: "blocks" });
    expect(initialModeView("modules", "build", "graph", modes, views)).toEqual({ mode: "modules", view: "graph" });
  });
});
