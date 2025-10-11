import type { NextRequest } from "next/server";

import { TRACE_HEADER_NAMES } from "../../../../app/api/trace";
import { GET } from "../../../../app/api/search/route";

function createRequest(query: string, init?: { headers?: Record<string, string> }): NextRequest {
  const url = new URL(`https://example.com/api/search?${query}`);
  const headers = new Headers(init?.headers);
  return { nextUrl: url, headers } as unknown as NextRequest;
}

function getFetchHeaders(fetchMock: jest.MockedFunction<typeof fetch>): Headers | undefined {
  const fetchOptions = fetchMock.mock.calls[0]?.[1] as { headers?: HeadersInit } | undefined;
  if (!fetchOptions?.headers) {
    return undefined;
  }
  return new Headers(fetchOptions.headers);
}

describe("/api/search proxy", () => {
  const originalFetch = global.fetch;
  const originalApiKey = process.env.THEO_SEARCH_API_KEY;

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalApiKey === undefined) {
      delete process.env.THEO_SEARCH_API_KEY;
    } else {
      process.env.THEO_SEARCH_API_KEY = originalApiKey;
    }
    jest.restoreAllMocks();
  });

  it("adds an Authorization header when the API key includes a Bearer prefix", async () => {
    process.env.THEO_SEARCH_API_KEY = "Bearer secret";
    const mockResponse = new Response("{}", {
      status: 200,
      headers: { "content-type": "application/json" },
    });
    const fetchSpy = jest.fn().mockResolvedValue(mockResponse) as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchSpy;

    const request = createRequest("q=faith");
    await GET(request);

    const headers = getFetchHeaders(fetchSpy);
    expect(headers?.get("Accept")).toBe("application/json");
    expect(headers?.get("Authorization")).toBe("Bearer secret");
  });

  it("sends a plain key via the X-API-Key header", async () => {
    process.env.THEO_SEARCH_API_KEY = "plain-key";
    const mockResponse = new Response("{}", {
      status: 200,
      headers: { "content-type": "application/json" },
    });
    const fetchSpy = jest.fn().mockResolvedValue(mockResponse) as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchSpy;

    const request = createRequest("q=hope");
    await GET(request);

    const headers = getFetchHeaders(fetchSpy);
    expect(headers?.get("Accept")).toBe("application/json");
    expect(headers?.get("X-API-Key")).toBe("plain-key");
  });

  it("bubbles a 401 response when the API key is not configured", async () => {
    delete process.env.THEO_SEARCH_API_KEY;
    const mockResponse = new Response("unauthorized", {
      status: 401,
      headers: { "content-type": "text/plain" },
    });
    const fetchMock = jest.fn().mockResolvedValue(mockResponse) as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchMock;

    const request = createRequest("q=love");
    const response = await GET(request);

    expect(response.status).toBe(401);
    const headers = getFetchHeaders(fetchMock);
    expect(headers?.get("Accept")).toBe("application/json");
    expect(headers?.has("Authorization")).toBe(false);
    expect(headers?.has("X-API-Key")).toBe(false);
  });

  it("forwards trace headers from the upstream search service", async () => {
    process.env.THEO_SEARCH_API_KEY = "plain-key";
    const traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01";
    const traceId = "abc123";
    const mockResponse = new Response("{}", {
      status: 200,
      headers: {
        "content-type": "application/json",
        traceparent,
        "x-trace-id": traceId,
      },
    });
    const fetchMock = jest.fn().mockResolvedValue(mockResponse) as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchMock;

    const request = createRequest("q=grace");
    const response = await GET(request);

    expect(response.headers.get("traceparent")).toBe(traceparent);
    expect(response.headers.get("x-trace-id")).toBe(traceId);
  });

  it("forwards trace headers from the client request to the upstream search service", async () => {
    process.env.THEO_SEARCH_API_KEY = "plain-key";
    const traceHeaders: Record<string, string> = {};
    for (const header of TRACE_HEADER_NAMES) {
      traceHeaders[header] = `${header}-value`;
    }
    const mockResponse = new Response("{}", {
      status: 200,
      headers: { "content-type": "application/json" },
    });
    const fetchMock = jest.fn().mockResolvedValue(mockResponse) as jest.MockedFunction<typeof fetch>;
    global.fetch = fetchMock;

    const request = createRequest("q=grace", { headers: traceHeaders });
    await GET(request);

    const headers = getFetchHeaders(fetchMock);
    expect(headers).toBeDefined();
    for (const header of TRACE_HEADER_NAMES) {
      expect(headers?.get(header)).toBe(traceHeaders[header]);
    }
  });
});
