import {
  ChatSessionState,
  ResearchPlan,
  parseGuardrailPayload,
  normaliseChatCompletion,
  normaliseChatSessionState,
  toOptionalString,
} from "./api-normalizers";
import type {
  GuardrailFailureMetadata,
  GuardrailSuggestion,
  HybridSearchFilters,
} from "./guardrails";
import { buildErrorMessage, TheoApiError, type HttpClient } from "./http";

type ResearchModeId = import("../mode-config").ResearchModeId;
type RAGAnswer = import("../copilot/components/types").RAGAnswer;

export type ChatSessionPreferencesPayload = import("./api-normalizers").ChatSessionPreferencesPayload;
export type ChatSessionMemoryEntry = import("./api-normalizers").ChatSessionMemoryEntry;

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
  | { type: "complete"; response: { sessionId: string; answer: RAGAnswer; plan: ResearchPlan | null } }
  | {
      type: "guardrail_violation";
      message: string;
      traceId?: string | null;
      suggestions?: GuardrailSuggestion[];
      metadata?: GuardrailFailureMetadata | null;
    };

export type ChatWorkflowSuccess = {
  kind: "success";
  sessionId: string;
  answer: RAGAnswer;
  plan: ResearchPlan | null;
};

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
      return { type: "answer_fragment", content: fragment } satisfies ChatWorkflowStreamEvent;
    }
  }

  const completion = normaliseChatCompletion(chunk, fallbackSessionId);
  if (completion) {
    return {
      type: "complete",
      response: {
        sessionId: completion.sessionId,
        answer: completion.answer,
        plan: completion.plan,
      },
    } satisfies ChatWorkflowStreamEvent;
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

export type ChatClient = {
  runChatWorkflow(payload: ChatWorkflowRequest, options?: ChatWorkflowOptions): Promise<ChatWorkflowResult>;
  fetchChatSession(sessionId: string): Promise<ChatSessionState | null>;
};

export function createChatClient(http: HttpClient): ChatClient {
  const runChatWorkflow: ChatClient["runChatWorkflow"] = async (payload, options) => {
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

    const response = await fetch(`${http.baseUrl}/ai/chat`, {
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
                    plan: interpreted.response.plan,
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
                plan: interpreted.response.plan,
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
      options?.onEvent?.({
        type: "guardrail_violation",
        message: guardrail.message,
        traceId: guardrail.traceId,
        suggestions: guardrail.suggestions,
        metadata: guardrail.metadata,
      });
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
      const success: ChatWorkflowSuccess = {
        kind: "success",
        sessionId: completion.sessionId,
        answer: completion.answer,
        plan: completion.plan,
      };
      options?.onEvent?.({
        type: "complete",
        response: {
          sessionId: completion.sessionId,
          answer: completion.answer,
          plan: completion.plan,
        },
      });
      return success;
    }

    throw new Error("Unexpected chat workflow response.");
  };

  const fetchChatSession: ChatClient["fetchChatSession"] = async (sessionId) => {
    const payload = await http.request(`/ai/chat/${encodeURIComponent(sessionId)}`);
    const normalised = normaliseChatSessionState(payload);
    return normalised;
  };

  return { runChatWorkflow, fetchChatSession };
}

export type ChatWorkflowClient = Pick<ChatClient, "runChatWorkflow" | "fetchChatSession">;
