import type { NextRequest } from "next/server";

import { GET } from "../../../../app/api/search/route";

function createRequest(query: string): NextRequest {
  const url = new URL(`https://example.com/api/search?${query}`);
  return { nextUrl: url } as unknown as NextRequest;
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

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.any(URL),
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
          Authorization: "Bearer secret",
        }),
      }),
    );
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

    expect(fetchSpy).toHaveBeenCalledWith(
      expect.any(URL),
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
          "X-API-Key": "plain-key",
        }),
      }),
    );
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
    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(URL),
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/json",
        }),
      }),
    );
    const fetchOptions = fetchMock.mock.calls[0]?.[1] as { headers?: Record<string, string> } | undefined;
    expect(fetchOptions?.headers).toBeDefined();
    const calledHeaders = fetchOptions?.headers ?? {};
    expect(calledHeaders).not.toHaveProperty("Authorization");
    expect(calledHeaders).not.toHaveProperty("X-API-Key");
  });
});
