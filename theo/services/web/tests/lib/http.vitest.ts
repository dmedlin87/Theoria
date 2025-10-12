import { afterEach, describe, expect, it, vi } from "vitest";

import {
  TheoApiError,
  buildErrorMessage,
  createHttpClient,
  handleResponse,
} from "../../app/lib/http";

describe("buildErrorMessage", () => {
  it("prefers server-provided bodies", () => {
    expect(buildErrorMessage(500, "Upstream error")).toBe("Upstream error");
  });

  it("falls back to a descriptive default", () => {
    expect(buildErrorMessage(404, null)).toBe("Request failed with status 404");
  });
});

describe("handleResponse", () => {
  it("returns nothing for successful no-content responses", async () => {
    const response = new Response(null, { status: 204 });
    await expect(handleResponse(response, true)).resolves.toBeUndefined();
  });

  it("raises a TheoApiError with nested detail text", async () => {
    const payload = {
      detail: { message: "Payload missing required field" },
    };
    const response = new Response(JSON.stringify(payload), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    });

    await expect(handleResponse(response.clone(), true)).rejects.toThrow(TheoApiError);
    await expect(handleResponse(response, true)).rejects.toMatchObject({
      status: 422,
      message: "Payload missing required field",
      payload,
    });
  });
});

describe("createHttpClient", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalFetch) {
      globalThis.fetch = originalFetch;
    } else {
      delete (globalThis as Record<string, unknown>).fetch;
    }
  });

  it("resolves the base URL and parses JSON by default", async () => {
    const json = { ok: true };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(json), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock;

    const client = createHttpClient("https://api.test/");
    const result = await client.request("/jobs", { method: "GET" });

    expect(fetchMock).toHaveBeenCalledWith("https://api.test/jobs", expect.any(Object));
    expect(result).toEqual(json);
  });

  it("honours parseJson flag and merges headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, { status: 200, headers: { "Content-Type": "text/plain" } }),
    );
    globalThis.fetch = fetchMock;

    const client = createHttpClient("https://api.test");
    await client.request("/upload", {
      method: "POST",
      body: JSON.stringify({ value: 1 }),
      headers: { Authorization: "Bearer token" },
      parseJson: false,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.test/upload",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer token",
        }),
      }),
    );
  });
});
