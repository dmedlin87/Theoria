import { getApiBaseUrl } from "./api";
import type { components } from "./generated/api";
import type {
  GuardrailFailureMetadata,
  GuardrailSuggestion,
  HybridSearchFilters,
} from "./guardrails";

type ExportDeliverableResponse = components["schemas"]["ExportDeliverableResponse"];
type ResearchModeId = import("../mode-config").ResearchModeId;
type RAGAnswer = import("../copilot/components/types").RAGAnswer;
type RAGCitation = import("../copilot/components/types").RAGCitation;
export type { HybridSearchFilters } from "./guardrails";

export type ChatSessionPreferencesPayload = {
  mode?: string | null;
  defaultFilters?: HybridSearchFilters | null;
  frequentlyOpenedPanels?: string[];
};

export type ChatSessionMemoryEntry = {
  question: string;
  answer: string;
  answerSummary?: string | null;
  citations: RAGCitation[];
  documentIds: string[];
  createdAt: string;
};

export type ChatSessionState = {
  sessionId: string;
  stance?: string | null;
  summary?: string | null;
  documentIds: string[];
  preferences?: {
    mode?: string | null;
    defaultFilters?: HybridSearchFilters | null;
    frequentlyOpenedPanels: string[];
  } | null;
  memory: ChatSessionMemoryEntry[];
  createdAt: string;
  updatedAt: string;
  lastInteractionAt: string;
};

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
  filters?: HybridSearchFilters | null;
  preferences?: ChatSessionPreferencesPayload | null;
};

export type ChatWorkflowStreamEvent =
  | { type: "answer_fragment"; content: string }
  | { type: "complete"; response: { sessionId: string; answer: RAGAnswer } }
  | {
      type: "guardrail_violation";
      message: string;
      traceId?: string | null;
      suggestions?: GuardrailSuggestion[];
      metadata?: GuardrailFailureMetadata | null;
    };

export type ChatWorkflowSuccess = { kind: "success"; sessionId: string; answer: RAGAnswer };

export type ChatWorkflowGuardrail = {
  kind: "guardrail";
  message: string;
  traceId?: string | null;
  suggestions: GuardrailSuggestion[];
  metadata: GuardrailFailureMetadata | null;
};

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

function coerceStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((entry) => toOptionalString(entry))
    .filter((entry): entry is string => entry !== null);
}

const GUARDRAIL_ACTIONS = new Set(["search", "upload", "retry", "none"]);
const GUARDRAIL_KINDS = new Set(["retrieval", "generation", "safety", "ingest"]);

function parseHybridFilters(value: unknown): HybridSearchFilters | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const filters: HybridSearchFilters = {};
  let hasValue = false;
  const assign = (key: keyof HybridSearchFilters, candidate: unknown) => {
    if (typeof candidate === "string") {
      const normalized = candidate.trim();
      if (normalized) {
        filters[key] = normalized;
        hasValue = true;
      }
    }
  };
  assign("collection", record.collection);
  assign("author", record.author);
  assign("source_type", record.source_type);
  assign("theological_tradition", record.theological_tradition);
  assign("topic_domain", record.topic_domain);
  return hasValue ? filters : null;
}

function parseGuardrailSuggestion(value: unknown): GuardrailSuggestion | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const label = toOptionalString(record.label);
  if (!label) {
    return null;
  }
  const action = (toOptionalString(record.action) ?? "search").toLowerCase();
  const description = toOptionalString(record.description);
  if (action === "upload") {
    return {
      action: "upload",
      label,
      description,
      collection: toOptionalString(record.collection),
    } satisfies GuardrailSuggestion;
  }
  return {
    action: "search",
    label,
    description,
    query: toOptionalString(record.query),
    osis: toOptionalString(record.osis),
    filters: parseHybridFilters(record.filters ?? null),
  } satisfies GuardrailSuggestion;
}

function parseGuardrailMetadata(value: unknown): GuardrailFailureMetadata | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const code = toOptionalString(record.code) ?? "guardrail_violation";
  const guardrailRaw = toOptionalString(record.guardrail)?.toLowerCase();
  const guardrail = guardrailRaw && GUARDRAIL_KINDS.has(guardrailRaw)
    ? (guardrailRaw as GuardrailFailureMetadata["guardrail"])
    : "unknown";
  const suggestedRaw =
    toOptionalString(record.suggested_action ?? record.suggestedAction)?.toLowerCase() ??
    (guardrail === "ingest" ? "upload" : "search");
  const suggestedAction = GUARDRAIL_ACTIONS.has(suggestedRaw)
    ? (suggestedRaw as GuardrailFailureMetadata["suggestedAction"])
    : (guardrail === "ingest" ? "upload" : "search");
  const safeRefusal =
    typeof record.safe_refusal === "boolean"
      ? record.safe_refusal
      : typeof record.safeRefusal === "boolean"
      ? record.safeRefusal
      : false;
  return {
    code,
    guardrail,
    suggestedAction,
    filters: parseHybridFilters(record.filters ?? null),
    safeRefusal,
    reason: toOptionalString(record.reason),
  } satisfies GuardrailFailureMetadata;
}

function buildGuardrailPayload(record: Record<string, unknown>) {
  const detailValue = record.detail;
  const detailRecord =
    detailValue && typeof detailValue === "object" ? (detailValue as Record<string, unknown>) : record;
  const detailString =
    typeof detailValue === "string" ? toOptionalString(detailValue) : undefined;
  const message =
    toOptionalString(detailRecord.message) ??
    detailString ??
    toOptionalString(record.message) ??
    "Response was blocked by content guardrails.";
  const traceId =
    toOptionalString(
      detailRecord.trace_id ??
        detailRecord.traceId ??
        detailRecord.trace ??
        record.trace_id ??
        record.traceId ??
        record.trace ??
        record.id ??
        record.reference,
    ) ?? null;
  const suggestionsSource =
    Array.isArray(detailRecord.suggestions) ? detailRecord.suggestions : [];
  const suggestions = suggestionsSource
    .map((entry) => parseGuardrailSuggestion(entry))
    .filter((entry): entry is GuardrailSuggestion => entry !== null);
  const metadataValue =
    detailRecord.metadata ??
    detailRecord.guardrail_metadata ??
    record.metadata ??
    null;
  const metadata = parseGuardrailMetadata(metadataValue);
  return { message, traceId, suggestions, metadata } satisfies {
    message: string;
    traceId: string | null;
    suggestions: GuardrailSuggestion[];
    metadata: GuardrailFailureMetadata | null;
  };
}

function parseGuardrailPayload(
  payload: unknown,
): { message: string; traceId: string | null; suggestions: GuardrailSuggestion[]; metadata: GuardrailFailureMetadata | null } | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const typeValue = toOptionalString(record.type) ?? toOptionalString(record.reason);
  if (typeValue && typeValue.toLowerCase().includes("guardrail")) {
    return buildGuardrailPayload(record);
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

function normaliseChatSessionState(payload: unknown): ChatSessionState | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const sessionId = toOptionalString(record.session_id ?? record.sessionId ?? record.id);
  if (!sessionId) {
    return null;
  }
  const stance = toOptionalString(record.stance);
  const summary = toOptionalString(record.summary);
  const createdAt = toOptionalString(record.created_at ?? record.createdAt);
  const updatedAt = toOptionalString(record.updated_at ?? record.updatedAt);
  const lastInteractionAt = toOptionalString(record.last_interaction_at ?? record.lastInteractionAt);

  const documentIds = coerceStringList(record.document_ids ?? record.documentIds);

  const memoryItems = Array.isArray(record.memory) ? record.memory : [];
  const memory: ChatSessionMemoryEntry[] = [];
  for (const item of memoryItems) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const data = item as Record<string, unknown>;
    const question = toOptionalString(data.question);
    const answer = toOptionalString(data.answer);
    if (!question || !answer) {
      continue;
    }
    const answerSummary = toOptionalString(data.answer_summary ?? data.answerSummary ?? null);
    const created = toOptionalString(data.created_at ?? data.createdAt) ?? new Date().toISOString();
    const citationsRaw = Array.isArray(data.citations) ? data.citations : [];
    const citations: RAGCitation[] = citationsRaw
      .map((citation) => normaliseCitation(citation))
      .filter((value): value is RAGCitation => value != null);
    const documentIdsEntry = coerceStringList(data.document_ids ?? data.documentIds);
    memory.push({
      question,
      answer,
      answerSummary,
      citations,
      documentIds: documentIdsEntry,
      createdAt: created,
    });
  }

  let preferences: ChatSessionState["preferences"] = null;
  if (record.preferences && typeof record.preferences === "object") {
    const pref = record.preferences as Record<string, unknown>;
    const mode = toOptionalString(pref.mode);
    const defaultFilters = pref.default_filters ?? pref.defaultFilters ?? null;
    const panelsSource = pref.frequently_opened_panels ?? pref.frequentlyOpenedPanels;
    const frequentlyOpenedPanels = Array.isArray(panelsSource)
      ? panelsSource
          .map((value: unknown) => toOptionalString(value))
          .filter((value): value is string => Boolean(value))
      : [];
    preferences = {
      mode,
      defaultFilters: (defaultFilters ?? null) as HybridSearchFilters | null,
      frequentlyOpenedPanels,
    };
  }

  const fallbackTimestamp = new Date().toISOString();

  return {
    sessionId,
    stance,
    summary,
    documentIds,
    preferences,
    memory,
    createdAt: createdAt ?? fallbackTimestamp,
    updatedAt: updatedAt ?? createdAt ?? fallbackTimestamp,
    lastInteractionAt: lastInteractionAt ?? updatedAt ?? createdAt ?? fallbackTimestamp,
  };
}

function interpretStreamChunk(
  chunk: unknown,
  fallbackSessionId: string | null,
): ChatWorkflowStreamEvent | ChatWorkflowGuardrail | null {
  const guardrail = parseGuardrailPayload(chunk);
  if (guardrail) {
    return {
      kind: "guardrail",
      message: guardrail.message,
      traceId: guardrail.traceId,
      suggestions: guardrail.suggestions,
      metadata: guardrail.metadata,
    } satisfies ChatWorkflowGuardrail;
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
      mode: payload.modeId,
      mode_id: payload.modeId,
    };
    const stance = payload.preferences?.mode ?? payload.modeId;
    if (stance) {
      requestBody.stance = stance;
    }
    if (payload.prompt != null) {
      requestBody.prompt = payload.prompt;
    }
    if (payload.osis != null) {
      requestBody.osis = payload.osis;
    }
    if (payload.filters) {
      requestBody.filters = payload.filters;
    }
    if (payload.preferences) {
      requestBody.preferences = {
        mode: payload.preferences.mode ?? stance ?? null,
        default_filters: payload.preferences.defaultFilters ?? null,
        frequently_opened_panels: payload.preferences.frequentlyOpenedPanels ?? [],
      };
    }

    const response = await fetch(`${this.baseUrl}/ai/chat`, {
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
        return {
          kind: "guardrail",
          message: guardrail.message,
          traceId: guardrail.traceId,
          suggestions: guardrail.suggestions,
          metadata: guardrail.metadata,
        } satisfies ChatWorkflowGuardrail;
      }
      let extracted: string | null = null;
      if (parsed && typeof parsed === "object") {
        const record = parsed as Record<string, unknown>;
        if (typeof record.message === "string") {
          extracted = toOptionalString(record.message);
        }
        if (!extracted && typeof record.detail === "string") {
          extracted = toOptionalString(record.detail);
        }
      }
      const errorMessage = extracted ?? buildErrorMessage(response.status, null);
      throw new TheoApiError(errorMessage, response.status, parsed);
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
                  const guardrailEvent: ChatWorkflowStreamEvent = {
                    type: "guardrail_violation",
                    message: interpreted.message,
                    traceId: interpreted.traceId ?? null,
                    suggestions: interpreted.suggestions,
                    metadata: interpreted.metadata,
                  };
                  options?.onEvent?.(guardrailEvent);
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
              const guardrailEvent: ChatWorkflowStreamEvent = {
                type: "guardrail_violation",
                message: interpreted.message,
                traceId: interpreted.traceId ?? null,
                suggestions: interpreted.suggestions,
                metadata: interpreted.metadata,
              };
              options?.onEvent?.(guardrailEvent);
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
      return {
        kind: "guardrail",
        message: guardrail.message,
        traceId: guardrail.traceId,
        suggestions: guardrail.suggestions,
        metadata: guardrail.metadata,
      } satisfies ChatWorkflowGuardrail;
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

  async fetchChatSession(sessionId: string): Promise<ChatSessionState | null> {
    const payload = await this.request(`/ai/chat/${encodeURIComponent(sessionId)}`);
    const normalised = normaliseChatSessionState(payload);
    return normalised;
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

export type ChatWorkflowClient = Pick<TheoApiClient, "runChatWorkflow" | "fetchChatSession">;
