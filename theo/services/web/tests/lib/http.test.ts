import { createHttpClient, TheoApiError } from "../../app/lib/http";

type MockResponseInit = {
  status: number;
  body?: string | null;
  headers?: Record<string, string>;
};

function createMockResponse({ status, body = "", headers = {} }: MockResponseInit): Response {
  const headerLookup = Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [key.toLowerCase(), value]),
  );
  const responseHeaders = {
    get(name: string) {
      return headerLookup[name.toLowerCase()] ?? null;
    },
  } as Headers;
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    headers: responseHeaders,
    async text() {
      return body ?? "";
    },
    async json() {
      if (!body) {
        throw new Error("No JSON body");
      }
      return JSON.parse(body);
    },
  } as unknown as Response;
}

describe("createHttpClient", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    if (originalFetch) {
      Object.defineProperty(globalThis, "fetch", {
        configurable: true,
        writable: true,
        value: originalFetch,
      });
    } else {
      Reflect.deleteProperty(globalThis, "fetch");
    }
    jest.restoreAllMocks();
  });

  it("includes response text for 404 errors", async () => {
    const fetchMock = jest.fn().mockResolvedValueOnce(
      createMockResponse({ status: 404, body: "Document not found" }),
    );
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
    const client = createHttpClient("https://api.test");
    await expect(client.request("/features/")).rejects.toThrow("Document not found");
    expect(fetchMock).toHaveBeenCalled();
  });

  it("propagates API error payloads for 400 responses", async () => {
    const fetchMock = jest.fn().mockResolvedValueOnce(
      createMockResponse({
        status: 400,
        body: JSON.stringify({ detail: "Invalid request" }),
        headers: { "content-type": "application/json" },
      }),
    );
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
    const client = createHttpClient("https://api.test");
    await expect(
      client.request("/ai/transcript/export", {
        method: "POST",
        body: JSON.stringify({ document_id: "doc", format: "markdown" }),
      }),
    ).rejects.toThrow("Invalid request");
  });

  it("falls back to status code messaging for empty 413 responses", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce(createMockResponse({ status: 413, body: null }));
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
    const client = createHttpClient("https://api.test");
    await expect(
      client.request(`/ai/digest/watchlists/watch-1`, { method: "DELETE", parseJson: false }),
    ).rejects.toThrow("Request failed with status 413");
  });

  it("attaches parsed payload to thrown TheoApiError", async () => {
    const fetchMock = jest.fn().mockResolvedValueOnce(
      createMockResponse({
        status: 422,
        body: JSON.stringify({ detail: { message: "Not allowed" }, metadata: { foo: "bar" } }),
        headers: { "content-type": "application/json" },
      }),
    );
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
    const client = createHttpClient("https://api.test");
    let caught: unknown;
    try {
      await client.request("/ai/digest");
    } catch (error) {
      caught = error;
    }
    expect(caught).toBeInstanceOf(TheoApiError);
    if (caught instanceof TheoApiError) {
      expect(caught.payload).toEqual({ detail: { message: "Not allowed" }, metadata: { foo: "bar" } });
    }
  });
});
