import { createChatClient } from "../../app/lib/chat-client";
import type { HttpClient } from "../../app/lib/http";

describe("createChatClient", () => {
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

  function createClient(): ReturnType<typeof createChatClient> {
    const httpClient: HttpClient = {
      baseUrl: "https://api.test",
      request: jest.fn() as HttpClient["request"],
    };
    return createChatClient(httpClient);
  }

  it("returns guardrail results when the API response is blocked", async () => {
    const guardrailResponse = {
      type: "guardrail_violation",
      detail: {
        message: "Blocked by guardrails",
        trace_id: "trace-1",
        suggestions: [
          { label: "Search again", action: "search", query: "creation" },
        ],
      },
    };
    const fetchMock = jest.fn().mockResolvedValueOnce({
      ok: false,
      status: 403,
      headers: {
        get(name: string) {
          return name.toLowerCase() === "content-type" ? "application/json" : null;
        },
      } as Headers,
      async json() {
        return guardrailResponse;
      },
      async text() {
        return JSON.stringify(guardrailResponse);
      },
    } as Response);
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });

    const client = createClient();
    const result = await client.runChatWorkflow({
      messages: [{ role: "user", content: "Tell me about Genesis" }],
      modeId: "synthesizer",
    });

    expect(result.kind).toBe("guardrail");
    if (result.kind === "guardrail") {
      expect(result.message).toBe("Blocked by guardrails");
      expect(result.traceId).toBe("trace-1");
      expect(result.suggestions).toHaveLength(1);
      const [suggestion] = result.suggestions;
      expect(suggestion?.action).toBe("search");
    }
  });

  it("falls back to JSON parsing when streaming is unavailable", async () => {
    const apiResponse = {
      answer: {
        summary: "In the beginning...",
        citations: [],
      },
      session_id: "session-42",
    };
    const fetchMock = jest.fn().mockResolvedValueOnce({
      ok: true,
      headers: {
        get(name: string) {
          return name.toLowerCase() === "content-type" ? "text/event-stream" : null;
        },
      } as Headers,
      body: null,
      async json() {
        return apiResponse;
      },
    } as Response);
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      writable: true,
      value: fetchMock,
    });

    const client = createClient();
    const events: unknown[] = [];
    const result = await client.runChatWorkflow(
      {
        messages: [{ role: "user", content: "Summarise Genesis 1" }],
        modeId: "synthesizer",
      },
      {
        onEvent(event) {
          events.push(event);
        },
      },
    );

    expect(result.kind).toBe("success");
    if (result.kind === "success") {
      expect(result.sessionId).toBe("session-42");
      expect(result.answer.summary).toContain("beginning");
    }
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ type: "complete", response: { sessionId: "session-42" } });
  });
});
