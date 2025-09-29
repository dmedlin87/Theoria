import { getApiBaseUrl } from "./api";
import type { components } from "./generated/api";

type ExportDeliverableResponse = components["schemas"]["ExportDeliverableResponse"];
type ResearchModeId = import("../mode-config").ResearchModeId;
type RAGAnswer = import("../copilot/components/types").RAGAnswer;
type RAGCitation = import("../copilot/components/types").RAGCitation;

export type ChatWorkflowMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type ChatWorkflowRequest = {
  messages: ChatWorkflowMessage[];
  modeId: ResearchModeId;
  sessionId?: string | null;
  prompt?: string | null;
  osis?: string | null;
};

export type ChatWorkflowStreamEvent =
  | { type: "answer_fragment"; content: string }
  | { type: "complete"; response: { sessionId: string; answer: RAGAnswer } }
  | { type: "guardrail_violation"; message: string; traceId?: string | null };

export type ChatWorkflowSuccess = { kind: "success"; sessionId: string; answer: RAGAnswer };

export type ChatWorkflowGuardrail = { kind: "guardrail"; message: string; traceId?: string | null };

export type ChatWorkflowResult = ChatWorkflowSuccess | ChatWorkflowGuardrail;

export type ChatWorkflowOptions = {
  signal?: AbortSignal;
  onEvent?: (event: ChatWorkflowStreamEvent) => void;
};

export class TheoApiError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "TheoApiError";
    this.status = status;
    this.payload = payload;
  }
}

function normaliseExportResponse(
  payload: ExportDeliverableResponse,
): import("../copilot/components/types").ExportPresetResult {
  return {
    preset: payload.preset,
    format: payload.format,
    filename: payload.filename,
    mediaType: payload.media_type,
    content: payload.content,
  };
}

function buildErrorMessage(status: number, body: string | null): string {
  if (body) {
    return body;
  }
  return `Request failed with status ${status}`;
}

function toOptionalString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function parseGuardrailPayload(payload: unknown): { message: string; traceId: string | null } | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const typeValue = toOptionalString(record.type) ?? toOptionalString(record.reason);
  if (typeValue && typeValue.toLowerCase().includes("guardrail")) {
    const message =
      toOptionalString(record.message) ??
      toOptionalString(record.detail) ??
      "Response was blocked by content guardrails.";
    const traceId =
      toOptionalString(record.trace_id ?? record.traceId ?? record.trace ?? record.id ?? record.reference) ?? null;
    return { message, traceId };
  }

  if (typeof record.guardrail === "object" && record.guardrail) {
    const nested = parseGuardrailPayload(record.guardrail);
    if (nested) {
      return nested;
    }
  }

  if (Array.isArray(record.detail)) {
    for (const item of record.detail) {
      const nested = parseGuardrailPayload(item);
      if (nested) {
        return nested;
      }
    }
  } else if (record.detail && typeof record.detail === "object") {
    const nested = parseGuardrailPayload(record.detail);
    if (nested) {
      return nested;
    }
  }

  return null;
}

function normaliseCitation(value: unknown): RAGCitation | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const index = typeof record.index === "number" ? record.index : null;
  const osis = toOptionalString(record.osis);
  const anchor = toOptionalString(record.anchor);
  const passageId = toOptionalString(record.passage_id);
  const documentId = toOptionalString(record.document_id);
  const snippet = toOptionalString(record.snippet);
  if (
    index == null ||
    !osis ||
    !anchor ||
    !passageId ||
    !documentId ||
    !snippet
  ) {
    return null;
  }
  return {
    index,
    osis,
    anchor,
    passage_id: passageId,
    document_id: documentId,
    snippet,
    document_title: toOptionalString(record.document_title),
    source_url: toOptionalString(record.source_url),
  };
}

function normaliseAnswer(value: unknown): RAGAnswer | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const summary = toOptionalString(record.summary) ?? "";
  const citations = Array.isArray(record.citations)
    ? record.citations.map(normaliseCitation).filter((citation): citation is RAGCitation => citation !== null)
    : [];
  const modelName = toOptionalString(record.model_name);
  const modelOutput = toOptionalString(record.model_output);
  const guardrailProfile =
    record.guardrail_profile && typeof record.guardrail_profile === "object"
      ? (record.guardrail_profile as Record<string, string>)
      : null;

  return {
    summary,
    citations,
    model_name: modelName ?? null,
    model_output: modelOutput ?? null,
    guardrail_profile: guardrailProfile,
  };
}

function normaliseChatCompletion(
  payload: unknown,
  fallbackSessionId: string | null,
): ChatWorkflowSuccess | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const answer = normaliseAnswer(record.answer ?? record.result ?? null);
  if (!answer) {
    return null;
  }
  const sessionId =
    toOptionalString(record.session_id ?? record.sessionId ?? record.id) ?? fallbackSessionId ?? "session";
  return { kind: "success", sessionId, answer };
}

function interpretStreamChunk(
  chunk: unknown,
  fallbackSessionId: string | null,
): ChatWorkflowStreamEvent | ChatWorkflowGuardrail | null {
  const guardrail = parseGuardrailPayload(chunk);
  if (guardrail) {
    return { kind: "guardrail", message: guardrail.message, traceId: guardrail.traceId };
  }

  if (chunk && typeof chunk === "object") {
    const record = chunk as Record<string, unknown>;
    const fragment =
      toOptionalString(record.delta) ??
      toOptionalString(record.text) ??
      toOptionalString(record.content) ??
      toOptionalString(record.token);
    if (fragment) {
      return { type: "answer_fragment", content: fragment };
    }
  }

  const completion = normaliseChatCompletion(chunk, fallbackSessionId);
  if (completion) {
    return { type: "complete", response: { sessionId: completion.sessionId, answer: completion.answer } };
  }

  return null;
}

function parseJsonLine(input: string): unknown {
  try {
    return JSON.parse(input);
  } catch {
    return null;
  }
}

async function handleResponse(
  response: Response,
  parseJson: false,
): Promise<void>;
async function handleResponse<T>(
  response: Response,
  parseJson: true,
): Promise<T>;
async function handleResponse<T>(
  response: Response,
  parseJson: boolean,
): Promise<T | void>;
async function handleResponse<T>(
  response: Response,
  parseJson: boolean,
): Promise<T | void> {
  if (!response.ok) {
    const bodyText = await response.text();
    const contentType = response.headers.get("content-type") ?? "";
    let payload: unknown = bodyText || null;
    if (contentType.includes("application/json") && bodyText) {
      try {
        payload = JSON.parse(bodyText) as unknown;
      } catch (parseError) {
        console.warn("Failed to parse error payload", parseError);
        payload = bodyText;
      }
    }
    let message = buildErrorMessage(response.status, bodyText || null);
    if (payload && typeof payload === "object") {
      const detail = (payload as Record<string, unknown>).detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object") {
        const nested = (detail as Record<string, unknown>).message;
        if (typeof nested === "string") {
          message = nested;
        }
      }
    }
    throw new TheoApiError(message, response.status, payload ?? bodyText);
  }
  if (!parseJson) {
    return;
  }
  if (response.status === 204) {
    return;
  }
  const data = (await response.json()) as unknown;
  // The generated OpenAPI types describe the JSON schema for this response.
  return data as T;
}

export type RequestOptions = RequestInit & { parseJson?: boolean };

export class TheoApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    const resolved = (baseUrl ?? getApiBaseUrl()).replace(/\/$/, "");
    this.baseUrl = resolved;
  }

  private async request(path: string, init: RequestOptions & { parseJson: false }): Promise<void>;
  private async request<T>(
    path: string,
    init?: RequestOptions & { parseJson?: true },
  ): Promise<T>;
  private async request<T>(path: string, init?: RequestOptions): Promise<T | void> {
    const { parseJson = true, headers, ...rest } = init ?? {};
    const response = await fetch(`${this.baseUrl}${path}`, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(headers ?? {}),
      },
      ...rest,
    });
    if (parseJson) {
      return handleResponse<T>(response, true);
    }
    return handleResponse(response, false);
  }

  fetchFeatures(): Promise<Record<string, boolean>> {
    return this.request<Record<string, boolean>>("/features/");
  }

  async runChatWorkflow(
    payload: ChatWorkflowRequest,
    options?: ChatWorkflowOptions,
  ): Promise<ChatWorkflowResult> {
    const requestBody: Record<string, unknown> = {
      messages: payload.messages,
      session_id: payload.sessionId ?? null,
      stance: payload.modeId,
      mode: payload.modeId,
      mode_id: payload.modeId,
    };
    if (payload.prompt != null) {
      requestBody.prompt = payload.prompt;
    }
    if (payload.osis != null) {
      requestBody.osis = payload.osis;
    }

    const response = await fetch(`${this.baseUrl}/ai/workflows/chat`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
      signal: options?.signal ?? null,
    });

    const fallbackSessionId = payload.sessionId ?? null;

    if (!response.ok) {
      let parsed: unknown = null;
      try {
        parsed = await response.json();
      } catch {
        try {
          const text = await response.text();
          parsed = text ? JSON.parse(text) : null;
        } catch {
          parsed = null;
        }
      }
      const guardrail = parseGuardrailPayload(parsed);
      if (guardrail) {
        return { kind: "guardrail", message: guardrail.message, traceId: guardrail.traceId };
      }
      const errorMessage =
        (parsed && typeof parsed === "object" && "message" in parsed && typeof parsed.message === "string"
          ? parsed.message
          : undefined) ?? buildErrorMessage(response.status, "");
      throw new Error(errorMessage);
    }

    const contentType = response.headers.get("content-type") ?? "";
    const isStreaming = Boolean(response.body) && /jsonl|ndjson|event-stream/i.test(contentType);

    if (isStreaming && response.body) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalResult: ChatWorkflowSuccess | null = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        let newlineIndex = buffer.indexOf("\n");
        while (newlineIndex !== -1) {
          const rawLine = buffer.slice(0, newlineIndex).trim();
          buffer = buffer.slice(newlineIndex + 1);
          const sanitized = rawLine.startsWith("data:") ? rawLine.slice(5).trim() : rawLine;
          if (sanitized) {
            const parsed = parseJsonLine(sanitized);
            if (parsed != null) {
              const interpreted = interpretStreamChunk(parsed, fallbackSessionId);
              if (interpreted) {
                if ("kind" in interpreted) {
                  options?.onEvent?.({
                    type: "guardrail_violation",
                    message: interpreted.message,
                    traceId: interpreted.traceId ?? null,
                  });
                  return interpreted;
                }
                if (interpreted.type === "complete") {
                  finalResult = {
                    kind: "success",
                    sessionId: interpreted.response.sessionId,
                    answer: interpreted.response.answer,
                  };
                }
                options?.onEvent?.(interpreted);
              }
            }
          }
          newlineIndex = buffer.indexOf("\n");
        }
      }

      buffer += decoder.decode();
      const trailingLine = buffer.trim();
      const trailing = trailingLine.startsWith("data:") ? trailingLine.slice(5).trim() : trailingLine;
      if (trailing) {
        const parsed = parseJsonLine(trailing);
        if (parsed != null) {
          const interpreted = interpretStreamChunk(parsed, fallbackSessionId);
          if (interpreted) {
            if ("kind" in interpreted) {
              options?.onEvent?.({
                type: "guardrail_violation",
                message: interpreted.message,
                traceId: interpreted.traceId ?? null,
              });
              return interpreted;
            }
            if (interpreted.type === "complete") {
              finalResult = {
                kind: "success",
                sessionId: interpreted.response.sessionId,
                answer: interpreted.response.answer,
              };
            }
            options?.onEvent?.(interpreted);
          }
        }
      }

      if (finalResult) {
        return finalResult;
      }
      throw new Error("Chat workflow completed without a final response.");
    }

    let jsonPayload: unknown = null;
    try {
      jsonPayload = await response.json();
    } catch {
      jsonPayload = null;
    }
    const guardrail = parseGuardrailPayload(jsonPayload);
    if (guardrail) {
      return { kind: "guardrail", message: guardrail.message, traceId: guardrail.traceId };
    }
    const completion = normaliseChatCompletion(jsonPayload, fallbackSessionId);
    if (completion) {
      options?.onEvent?.({
        type: "complete",
        response: { sessionId: completion.sessionId, answer: completion.answer },
      });
      return completion;
    }

    throw new Error("Unexpected chat workflow response.");
  }

  runVerseWorkflow(payload: {
    model: string;
    osis?: string | null;
    passage?: string | null;
    question?: string | null;
  }): Promise<import("../copilot/components/types").VerseResponse> {
    return this.request("/ai/verse", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runSermonWorkflow(payload: {
    model: string;
    topic: string;
    osis?: string | null;
  }): Promise<import("../copilot/components/types").SermonResponse> {
    return this.request("/ai/sermon-prep", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runComparativeWorkflow(payload: {
    model: string;
    osis: string;
    participants: string[];
  }): Promise<import("../copilot/components/types").ComparativeResponse> {
    return this.request("/ai/comparative", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runMultimediaWorkflow(payload: {
    model: string;
    collection?: string | null;
  }): Promise<import("../copilot/components/types").MultimediaDigestResponse> {
    return this.request("/ai/multimedia", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runDevotionalWorkflow(payload: {
    model: string;
    osis: string;
    focus: string;
  }): Promise<import("../copilot/components/types").DevotionalResponse> {
    return this.request("/ai/devotional", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runCollaborationWorkflow(payload: {
    model: string;
    thread: string;
    osis: string;
    viewpoints: string[];
  }): Promise<import("../copilot/components/types").CollaborationResponse> {
    return this.request("/ai/collaboration", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runCurationWorkflow(payload: {
    model: string;
    since?: string | null;
  }): Promise<import("../copilot/components/types").CorpusCurationReport> {
    return this.request("/ai/curation", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runSermonExport(payload: {
    model: string;
    topic: string;
    osis?: string | null;
    format: string;
  }): Promise<import("../copilot/components/types").ExportPresetResult> {
    return this.request<ExportDeliverableResponse>(
      "/ai/sermon-prep/export?format=" + encodeURIComponent(payload.format),
      {
        method: "POST",
        body: JSON.stringify({
          model: payload.model,
          topic: payload.topic,
          osis: payload.osis ?? null,
        }),
      },
    ).then(normaliseExportResponse);
  }

  runTranscriptExport(payload: {
    documentId: string;
    format: string;
  }): Promise<import("../copilot/components/types").ExportPresetResult> {
    return this.request<ExportDeliverableResponse>("/ai/transcript/export", {
      method: "POST",
      body: JSON.stringify({
        document_id: payload.documentId,
        format: payload.format,
      }),
    }).then(normaliseExportResponse);
  }

  exportCitations(
    payload: components["schemas"]["CitationExportRequest"],
  ): Promise<import("../copilot/components/types").CitationExportResponse> {
    return this.request("/ai/citations/export", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  getDigest(): Promise<import("../admin/digests/types").TopicDigest> {
    return this.request("/ai/digest");
  }

  refreshDigest(hours: number): Promise<import("../admin/digests/types").TopicDigest> {
    return this.request(`/ai/digest?hours=${hours}`, {
      method: "POST",
    });
  }

  listWatchlists(userId: string): Promise<import("../admin/digests/types").WatchlistResponse[]> {
    return this.request(`/ai/digest/watchlists?user_id=${encodeURIComponent(userId)}`);
  }

  createWatchlist(payload: import("../admin/digests/types").CreateWatchlistPayload): Promise<
    import("../admin/digests/types").WatchlistResponse
  > {
    return this.request("/ai/digest/watchlists", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  updateWatchlist(
    watchlistId: string,
    payload: import("../admin/digests/types").WatchlistUpdatePayload,
  ): Promise<import("../admin/digests/types").WatchlistResponse> {
    return this.request(`/ai/digest/watchlists/${watchlistId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  deleteWatchlist(watchlistId: string): Promise<void> {
    return this.request(`/ai/digest/watchlists/${watchlistId}`, {
      method: "DELETE",
      parseJson: false,
    });
  }

  runWatchlist(
    watchlistId: string,
    type: "preview" | "run",
  ): Promise<import("../admin/digests/types").WatchlistRunResponse> {
    const path =
      type === "preview"
        ? `/ai/digest/watchlists/${watchlistId}/preview`
        : `/ai/digest/watchlists/${watchlistId}/run`;
    const method = type === "preview" ? "GET" : "POST";
    return this.request(path, { method });
  }

  fetchWatchlistEvents(
    watchlistId: string,
    since?: string,
  ): Promise<import("../admin/digests/types").WatchlistRunResponse[]> {
    const query = since ? `?since=${encodeURIComponent(since)}` : "";
    return this.request(`/ai/digest/watchlists/${watchlistId}/events${query}`);
  }
}

export function createTheoApiClient(baseUrl?: string): TheoApiClient {
  return new TheoApiClient(baseUrl);
}

export type ChatWorkflowClient = Pick<TheoApiClient, "runChatWorkflow">;
