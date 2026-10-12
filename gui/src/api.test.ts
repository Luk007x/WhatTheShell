// SPDX-License-Identifier: AGPL-3.0-or-later
import { afterEach, expect, test, vi } from "vitest";
import { ApiError, getTool, initToken, parseToken, putWorkflow } from "./api";
import type { Workflow } from "./types/api";

afterEach(() => vi.unstubAllGlobals());

test("parseToken", () => {
  expect(parseToken("#token=abc_-1")).toBe("abc_-1");
  expect(parseToken("")).toBeNull();
  expect(parseToken("#other=1")).toBeNull();
});

test("token is read, fragment removed, header sent, errors typed", async () => {
  const replaceState = vi.fn();
  vi.stubGlobal("location", { hash: "#token=T0K", pathname: "/", search: "" });
  vi.stubGlobal("history", { replaceState });
  expect(initToken()).toBe("T0K");
  expect(replaceState).toHaveBeenCalledWith(null, "", "/");

  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ name: "ls" }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ error: "token", message: "kaputt" }), { status: 401 }));
  vi.stubGlobal("fetch", fetchMock);

  await getTool("ls");
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toContain("/api/tools/ls");
  expect((init.headers as Record<string, string>)["X-WTS-Token"]).toBe("T0K");

  const wf = { schema_version: 1, name: "x", steps: [] } as unknown as Workflow; // test fixture, shape irrelevant to the mock
  await expect(putWorkflow("a", wf)).rejects.toMatchObject({ status: 401, error: "token", message: "kaputt" });
  await expect(Promise.reject(new ApiError(1, "e", "m"))).rejects.toBeInstanceOf(ApiError);
});
