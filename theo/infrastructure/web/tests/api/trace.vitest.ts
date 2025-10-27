import { describe, expect, it } from "vitest";

import { forwardTraceHeaders } from "../../app/api/trace";

describe("forwardTraceHeaders", () => {
  it("copies only non-empty values and trims whitespace", () => {
    const source = new Headers({
      traceparent: " 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01 ",
      "x-trace-id": "   abc123   ",
      "x-request-id": "", // should be ignored
      "x-debug-report-id": "   \t\t   ",
    });
    const target = new Headers();

    forwardTraceHeaders(source, target);

    expect(target.get("traceparent")).toBe(
      "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    );
    expect(target.get("x-trace-id")).toBe("abc123");
    expect(target.has("x-request-id")).toBe(false);
    expect(target.has("x-debug-report-id")).toBe(false);
  });
});
