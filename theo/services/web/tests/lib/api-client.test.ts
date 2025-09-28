import { TheoApiClient } from "../../app/lib/api-client";

function createMockResponse(status: number, body: string | null, statusText?: string) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: statusText ?? "",
    text: async () => body ?? "",
  };
}

describe("TheoApiClient error handling", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    if (originalFetch) {
      Object.defineProperty(globalThis, "fetch", {
        configurable: true,
        writable: true,
        value: originalFetch,
      });
    } else {
      delete (globalThis as { fetch?: unknown }).fetch;
    }
    jest.restoreAllMocks();
  });

  it("includes response text for 404 errors", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce(createMockResponse(404, "Document not found", "Not Found"));
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
    const client = new TheoApiClient("https://api.test");
    await expect(client.fetchFeatures()).rejects.toThrow("Document not found");
    expect(fetchMock).toHaveBeenCalled();
  });

  it("propagates API error payloads for 400 responses", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce(createMockResponse(400, "Invalid request", "Bad Request"));
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
    const client = new TheoApiClient("https://api.test");
    await expect(
      client.runTranscriptExport({ documentId: "doc", format: "markdown" }),
    ).rejects.toThrow("Invalid request");
  });

  it("falls back to status code messaging for empty 413 responses", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce(createMockResponse(413, null, "Payload Too Large"));
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });
    const client = new TheoApiClient("https://api.test");
    await expect(client.deleteWatchlist("watch-1")).rejects.toThrow(
      "Request failed with status 413",
    );
  });
});
