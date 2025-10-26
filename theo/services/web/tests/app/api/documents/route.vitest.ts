import type { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hoisted = vi.hoisted(() => ({
  fetchWithTimeoutMock: vi.fn(),
}));

vi.mock("../../../../app/api/utils/fetchWithTimeout", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../../app/api/utils/fetchWithTimeout")>();
  return {
    ...actual,
    fetchWithTimeout: hoisted.fetchWithTimeoutMock,
  };
});

const fetchWithTimeoutMock = hoisted.fetchWithTimeoutMock;

import { GET } from "../../../../app/api/documents/route";
import { TimeoutError } from "../../../../app/api/utils/fetchWithTimeout";

function createRequest(path: string, headers?: Record<string, string>): NextRequest {
  const url = new URL(`https://web.test${path}`);
  return { nextUrl: url, headers: new Headers(headers) } as unknown as NextRequest;
}

describe("GET /api/documents", () => {
  const originalBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  beforeEach(() => {
    fetchWithTimeoutMock.mockReset();
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.com/base/";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalBaseUrl === undefined) {
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
    } else {
      process.env.NEXT_PUBLIC_API_BASE_URL = originalBaseUrl;
    }
  });

  it("proxies successful responses and forwards headers", async () => {
    const upstreamResponse = new Response("{\"items\":[]}", {
      status: 200,
      headers: {
        "content-type": "application/json",
        "x-trace-id": "upstream-trace",
        "x-request-id": "req-123",
      },
    });
    fetchWithTimeoutMock.mockResolvedValueOnce(upstreamResponse);

    const request = createRequest("/api/documents?query=faith&page=2", {
      authorization: "  Bearer token  ",
      "x-trace-id": " incoming-trace ",
      "x-request-id": "incoming-request",
      "x-api-key": "   ",
      cookie: " session=value ",
    });

    const response = await GET(request);

    expect(fetchWithTimeoutMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchWithTimeoutMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.example.com/base/documents?query=faith&page=2");

    const forwardedHeaders = new Headers(init.headers);
    expect(forwardedHeaders.get("authorization")).toBe("Bearer token");
    expect(forwardedHeaders.get("cookie")).toBe("session=value");
    expect(forwardedHeaders.get("x-trace-id")).toBe("incoming-trace");
    expect(forwardedHeaders.get("x-request-id")).toBe("incoming-request");
    expect(forwardedHeaders.has("x-api-key")).toBe(false);

    expect(response.status).toBe(200);
    expect(await response.text()).toBe("{\"items\":[]}");
    expect(response.headers.get("content-type")).toBe("application/json");
    expect(response.headers.get("x-trace-id")).toBe("upstream-trace");
    expect(response.headers.get("x-request-id")).toBe("req-123");
  });

  it("returns a proxy error response when the upstream request fails", async () => {
    const cryptoRef = globalThis.crypto;
    if (!cryptoRef || typeof cryptoRef.randomUUID !== "function") {
      throw new Error("crypto.randomUUID is not available in the test environment");
    }
    vi.spyOn(cryptoRef, "randomUUID").mockReturnValue("trace-timeout");
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    fetchWithTimeoutMock.mockRejectedValueOnce(new TimeoutError("Request timed out"));

    const response = await GET(createRequest("/api/documents"));

    expect(fetchWithTimeoutMock).toHaveBeenCalledTimes(1);
    const [url] = fetchWithTimeoutMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.example.com/base/documents");
    expect(response.status).toBe(504);
    expect(response.headers.get("x-trace-id")).toBe("trace-timeout");

    const payload = await response.json();
    expect(payload.traceId).toBe("trace-timeout");
    expect(payload.message).toContain("Documents service is currently unavailable");
    expect(payload.message).toContain("took too long");
    expect(payload.errorType).toBe("TimeoutError");
    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to proxy documents request",
      expect.any(TimeoutError),
    );
  });
});
