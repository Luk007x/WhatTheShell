// SPDX-License-Identifier: AGPL-3.0-or-later
import { afterEach, expect, test, vi } from "vitest";
import { ApiError, getTool, initToken, parseToken, putWorkflow } from "./api";
import type { Workflow } from "./types/api";
import { getLang } from "./i18n";

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

test("ok response without body is an error", async () => {
  vi.stubGlobal("location", { hash: "", pathname: "/", search: "" });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 200 })));
  await expect(getTool("ls")).rejects.toMatchObject({ error: "body" });
});

test("wsUrl appends token and lang, header X-WTS-Lang is sent", async () => {
  vi.stubGlobal("location", { hash: "", pathname: "/", search: "", protocol: "http:", host: "h:1" });
  const { wsUrl, getStatus } = await import("./api");
  expect(wsUrl("/ws/runs/r1")).toBe(`ws://h:1/ws/runs/r1?token=T0K&lang=${getLang()}`);
  expect(wsUrl("/ws/x?a=1")).toBe(`ws://h:1/ws/x?a=1&token=T0K&lang=${getLang()}`);
  const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  await getStatus();
  expect((fetchMock.mock.calls[0] as [string, RequestInit])[1].headers).toMatchObject({ "X-WTS-Lang": getLang() });
});
