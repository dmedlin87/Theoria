import { afterEach, describe, expect, it, vi } from "vitest";

import { createProxyErrorResponse } from "../../../app/api/utils/proxyError";
import { NetworkError, TimeoutError } from "../../../app/api/utils/fetchWithTimeout";

describe("createProxyErrorResponse", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mockRandomUUID(value: string) {
    const cryptoRef = globalThis.crypto;
    if (!cryptoRef || typeof cryptoRef.randomUUID !== "function") {
      throw new Error("crypto.randomUUID is not available in the test environment");
    }
    return vi.spyOn(cryptoRef, "randomUUID").mockReturnValue(value);
  }

  it("attaches a generated trace ID to the response and logs the context", async () => {
    mockRandomUUID("trace-123");
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const response = createProxyErrorResponse({
      message: "Upstream unavailable",
      logContext: "documents proxy",
    });

    expect(response.status).toBe(503);
    expect(response.headers.get("x-trace-id")).toBe("trace-123");

    const payload = await response.json();
    expect(payload).toEqual({
      message: "Upstream unavailable",
      traceId: "trace-123",
      errorType: "UnknownError",
    });
    expect(consoleSpy).toHaveBeenCalledWith("documents proxy");
  });

  it("overrides the status and message for timeout errors", async () => {
    mockRandomUUID("trace-timeout");
    const error = new TimeoutError("Request timed out");
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const response = createProxyErrorResponse({
      message: "Documents unavailable",
      status: 502,
      error,
      logContext: "timeout proxy",
    });

    expect(response.status).toBe(504);
    expect(response.headers.get("x-trace-id")).toBe("trace-timeout");

    const payload = await response.json();
    expect(payload.message).toContain("Documents unavailable");
    expect(payload.message).toContain("took too long");
    expect(payload.errorType).toBe("TimeoutError");
    expect(payload.traceId).toBe("trace-timeout");
    expect(consoleSpy).toHaveBeenCalledWith("timeout proxy", error);
  });

  it("overrides the status and message for network errors", async () => {
    mockRandomUUID("trace-network");
    const error = new NetworkError("Connection refused");
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const response = createProxyErrorResponse({
      message: "Documents unavailable",
      error,
    });

    expect(response.status).toBe(502);
    expect(response.headers.get("x-trace-id")).toBe("trace-network");

    const payload = await response.json();
    expect(payload.message).toContain("Documents unavailable");
    expect(payload.message).toContain("Unable to connect");
    expect(payload.errorType).toBe("NetworkError");
    expect(consoleSpy).toHaveBeenCalledWith("Documents unavailable", error);
  });
});
