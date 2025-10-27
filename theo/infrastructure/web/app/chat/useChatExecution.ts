import { useCallback, useRef, type RefObject } from "react";
import type { ChatWorkflowClient, ChatWorkflowMessage, ChatWorkflowStreamEvent } from "../lib/chat-client";
import type { ChatSessionPreferencesPayload } from "../lib/api-normalizers";
import type { HybridSearchFilters, GuardrailSuggestion } from "../lib/guardrails";
import { TheoApiError } from "../lib/http";
import type {
  ChatWorkspaceDispatch,
  ConversationEntry,
  AssistantConversationEntry,
} from "./useChatWorkspaceState";

type ResearchModeId = import("../mode-config").ResearchModeId;

function createMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 10);
}

export function useChatExecution(
  clientRef: RefObject<ChatWorkflowClient>,
  dispatch: ChatWorkspaceDispatch,
  conversation: ConversationEntry[],
  sessionId: string | null,
  modeId: ResearchModeId,
  defaultFilters: HybridSearchFilters | null,
  frequentlyOpenedPanels: string[],
  buildFallbackSuggestions: (question: string | null) => GuardrailSuggestion[]
) {
  const abortControllerRef = useRef<AbortController | null>(null);
  const conversationRef = useRef<ConversationEntry[]>(conversation);

  // Keep conversation ref in sync
  conversationRef.current = conversation;

  const applyStreamEvent = useCallback(
    (assistantId: string, event: ChatWorkflowStreamEvent) => {
      if (event.type === "answer_fragment") {
        dispatch({
          type: "UPDATE_ASSISTANT_FRAGMENT",
          assistantId,
          content: event.content,
        });
        return;
      }

      if (event.type === "guardrail_violation") {
        dispatch({ type: "REMOVE_ENTRY", entryId: assistantId });
        dispatch({
          type: "SET_GUARDRAIL",
          guardrail: {
            message: event.message,
            traceId: event.traceId ?? null,
            suggestions: event.suggestions ?? [],
            metadata: event.metadata ?? null,
          },
        });
        dispatch({ type: "STREAMING_COMPLETE", sessionId: null });
        abortControllerRef.current?.abort();
        abortControllerRef.current = null;
        return;
      }

      if (event.type === "complete") {
        dispatch({
          type: "UPDATE_ASSISTANT_COMPLETE",
          assistantId,
          payload: {
            content: event.response.answer.summary,
            citations: event.response.answer.citations ?? [],
            fallacyWarnings: event.response.answer.fallacy_warnings ?? [],
            reasoningTrace: event.response.answer.reasoning_trace ?? null,
          },
        });
        dispatch({ type: "STREAMING_COMPLETE", sessionId: event.response.sessionId });
        return;
      }
    },
    [dispatch]
  );

  const executeChat = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed) {
        return;
      }

      const userEntry: ConversationEntry = {
        id: createMessageId(),
        role: "user",
        content: trimmed,
      };

      const assistantId = createMessageId();
      const assistantEntry: AssistantConversationEntry = {
        id: assistantId,
        role: "assistant",
        content: "",
        citations: [],
        fallacyWarnings: [],
        prompt: trimmed,
        reasoningTrace: null,
      };

      dispatch({
        type: "START_STREAMING",
        payload: { userEntry, assistantEntry, question: trimmed },
      });

      // Build message history from current conversation state
      const historyMessages: ChatWorkflowMessage[] = [...conversationRef.current, userEntry]
        .filter(
          (entry): entry is ConversationEntry =>
            entry.role === "user" || entry.role === "assistant"
        )
        .map((entry) => ({ role: entry.role, content: entry.content }));

      const controller = new AbortController();
      abortControllerRef.current?.abort();
      abortControllerRef.current = controller;

      try {
        const preferencesPayload: ChatSessionPreferencesPayload = {
          mode: modeId,
          defaultFilters: defaultFilters ?? null,
          frequentlyOpenedPanels,
        };

        if (!clientRef.current) {
          throw new Error("Chat client not initialized");
        }

        const result = await clientRef.current.runChatWorkflow(
          {
            messages: historyMessages,
            modeId,
            sessionId,
            prompt: trimmed,
            filters: defaultFilters ?? null,
            preferences: preferencesPayload,
          },
          {
            signal: controller.signal,
            onEvent: (event) => applyStreamEvent(assistantId, event),
          }
        );

        if (result.kind === "success") {
          dispatch({ type: "SET_SESSION_ID", sessionId: result.sessionId });
          dispatch({
            type: "UPDATE_ASSISTANT_COMPLETE",
            assistantId,
            payload: {
              content: result.answer.summary,
              citations: result.answer.citations ?? [],
              fallacyWarnings: result.answer.fallacy_warnings ?? [],
              reasoningTrace: result.answer.reasoning_trace ?? null,
            },
          });
        } else if (result.kind === "guardrail") {
          dispatch({ type: "REMOVE_ENTRY", entryId: assistantId });
          dispatch({
            type: "SET_GUARDRAIL",
            guardrail: {
              message: result.message,
              traceId: result.traceId ?? null,
              suggestions: result.suggestions ?? [],
              metadata: result.metadata ?? null,
            },
          });
        }
      } catch (error) {
        dispatch({ type: "REMOVE_ENTRY", entryId: assistantId });

        if (error instanceof TheoApiError && error.status === 400) {
          const suggestions = buildFallbackSuggestions(trimmed);
          dispatch({
            type: "SET_GUARDRAIL",
            guardrail: {
              message: error.message,
              traceId: null,
              suggestions,
              metadata: {
                code: "chat_request_invalid",
                guardrail: "unknown",
                suggestedAction: suggestions[0]?.action ?? "search",
                filters: defaultFilters ?? null,
                safeRefusal: false,
                reason: error.message,
              },
            },
          });
          dispatch({ type: "SET_ERROR", error: null });
        } else {
          const message =
            error instanceof Error
              ? error.message
              : "We couldn't complete that chat request.";
          dispatch({ type: "SET_ERROR", error: message });
        }
      } finally {
        dispatch({ type: "STREAMING_COMPLETE", sessionId: null });
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
      }
    },
    [
      dispatch,
      applyStreamEvent,
      clientRef,
      sessionId,
      modeId,
      defaultFilters,
      frequentlyOpenedPanels,
      buildFallbackSuggestions,
    ]
  );

  const abortCurrentRequest = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
  }, []);

  return {
    executeChat,
    abortCurrentRequest,
  };
}
