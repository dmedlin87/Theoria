"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import ErrorCallout, { type ErrorCalloutProps } from "../components/ErrorCallout";
import type {
  ChatSessionPreferencesPayload,
  ChatSessionState,
  ChatWorkflowClient,
  ChatWorkflowMessage,
  ChatWorkflowStreamEvent,
  HybridSearchFilters,
} from "../lib/api-client";
import { TheoApiError, createTheoApiClient } from "../lib/api-client";
import {
  type GuardrailFailureMetadata,
  type GuardrailSuggestion,
  useGuardrailActions,
} from "../lib/guardrails";
import type { RAGCitation } from "../copilot/components/types";
import { useMode } from "../mode-context";

function createMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 10);
}

type ConversationEntry =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; content: string; citations: RAGCitation[] };

type AssistantConversationEntry = Extract<ConversationEntry, { role: "assistant" }>;

type GuardrailState =
  | {
      message: string;
      traceId: string | null;
      suggestions: GuardrailSuggestion[];
      metadata: GuardrailFailureMetadata | null;
    }
  | null;

type ChatWorkspaceProps = {
  client?: ChatWorkflowClient;
  initialPrompt?: string;
  autoSubmit?: boolean;
};

const CHAT_SESSION_STORAGE_KEY = "theo.chat.lastSessionId";

export default function ChatWorkspace({
  client,
  initialPrompt,
  autoSubmit = false,
}: ChatWorkspaceProps): JSX.Element {
  const { mode } = useMode();
  const handleGuardrailSuggestion = useGuardrailActions();
  const [fallbackClient] = useState(() => createTheoApiClient());
  const activeClient = client ?? fallbackClient;
  const clientRef = useRef<ChatWorkflowClient>(activeClient);
  useEffect(() => {
    clientRef.current = activeClient;
  }, [activeClient]);

  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const conversationRef = useRef<ConversationEntry[]>(conversation);
  useEffect(() => {
    conversationRef.current = conversation;
  }, [conversation]);

  const [inputValue, setInputValue] = useState(initialPrompt ?? "");
  useEffect(() => {
    if (typeof initialPrompt === "string") {
      setInputValue(initialPrompt);
    }
  }, [initialPrompt]);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const [frequentlyOpenedPanels, setFrequentlyOpenedPanels] = useState<string[]>([]);
  const [defaultFilters, setDefaultFilters] = useState<HybridSearchFilters | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeAssistantId, setActiveAssistantId] = useState<string | null>(null);
  const [guardrail, setGuardrail] = useState<GuardrailState>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const autoSubmitRef = useRef(false);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      setIsRestoring(false);
      return;
    }
    let cancelled = false;
    const storedId = window.localStorage.getItem(CHAT_SESSION_STORAGE_KEY);
    if (!storedId) {
      setIsRestoring(false);
      return;
    }

    const restoreSession = async () => {
      try {
        const state: ChatSessionState | null = await clientRef.current.fetchChatSession(storedId);
        if (cancelled) {
          return;
        }
        if (!state) {
          window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
          setIsRestoring(false);
          return;
        }
        setSessionId(state.sessionId);
        if (state.preferences?.frequentlyOpenedPanels) {
          setFrequentlyOpenedPanels(state.preferences.frequentlyOpenedPanels);
        } else {
          setFrequentlyOpenedPanels([]);
        }
        if (state.preferences?.defaultFilters) {
          setDefaultFilters(state.preferences.defaultFilters);
        } else {
          setDefaultFilters(null);
        }
        const restoredConversation: ConversationEntry[] = [];
        state.memory.forEach((entry) => {
          restoredConversation.push({
            id: createMessageId(),
            role: "user",
            content: entry.question,
          });
          restoredConversation.push({
            id: createMessageId(),
            role: "assistant",
            content: entry.answer,
            citations: entry.citations ?? [],
          });
        });
        if (restoredConversation.length > 0) {
          const lastUser = restoredConversation
            .slice()
            .reverse()
            .find((entry) => entry.role === "user");
          setLastQuestion(lastUser?.content ?? null);
        }
        setConversation(restoredConversation);
      } catch (error) {
        console.warn("Failed to restore chat session", error);
        window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
      } finally {
        if (!cancelled) {
          setIsRestoring(false);
        }
      }
    };

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, [activeClient]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (sessionId) {
      window.localStorage.setItem(CHAT_SESSION_STORAGE_KEY, sessionId);
    } else {
      window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
    }
  }, [sessionId]);

  const updateAssistantEntry = useCallback(
    (id: string, transform: (entry: AssistantConversationEntry) => AssistantConversationEntry) => {
      setConversation((previous) =>
        previous.map((entry) => {
          if (entry.id === id && entry.role === "assistant") {
            return transform(entry);
          }
          return entry;
        }),
      );
    },
    [],
  );

  const removeEntryById = useCallback((id: string) => {
    setConversation((previous) => previous.filter((entry) => entry.id !== id));
  }, []);

  const buildFallbackSuggestions = useCallback(
    (questionHint: string | null): GuardrailSuggestion[] => {
      const searchSuggestion: GuardrailSuggestion = {
        action: "search",
        label: "Search related passages",
        description:
          "Open the search workspace to inspect passages that align with your guardrail settings before retrying.",
        query: questionHint ?? null,
        osis: null,
        filters: defaultFilters ?? null,
      };
      const uploadSuggestion: GuardrailSuggestion = {
        action: "upload",
        label: "Upload supporting documents",
        description: "Add material covering this topic so Theo Engine has grounded sources next time.",
        collection: defaultFilters?.collection ?? null,
      };
      return [searchSuggestion, uploadSuggestion];
    },
    [defaultFilters],
  );

  const applyStreamEvent = useCallback(
    (assistantId: string, event: ChatWorkflowStreamEvent) => {
      if (event.type === "answer_fragment") {
        updateAssistantEntry(assistantId, (entry) => ({
          ...entry,
          content: entry.content + event.content,
        }));
        return;
      }
      if (event.type === "guardrail_violation") {
        removeEntryById(assistantId);
        setGuardrail({
          message: event.message,
          traceId: event.traceId ?? null,
          suggestions: event.suggestions ?? [],
          metadata: event.metadata ?? null,
        });
        setActiveAssistantId(null);
        setIsStreaming(false);
        abortControllerRef.current?.abort();
        abortControllerRef.current = null;
        return;
      }
      if (event.type === "complete") {
        setSessionId(event.response.sessionId);
        updateAssistantEntry(assistantId, (entry) => ({
          ...entry,
          content: event.response.answer.summary,
          citations: event.response.answer.citations ?? [],
        }));
        setActiveAssistantId(null);
        return;
      }
    },
    [removeEntryById, updateAssistantEntry],
  );

  const executeChat = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed) {
        setInputValue("");
        return;
      }

      const baseConversation = conversationRef.current;
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
      };

      setConversation([...baseConversation, userEntry, assistantEntry]);
      setActiveAssistantId(assistantId);
      setGuardrail(null);
      setErrorMessage(null);
      setLastQuestion(trimmed);
      setInputValue("");
      setIsStreaming(true);

      const historyMessages: ChatWorkflowMessage[] = [...baseConversation, userEntry]
        .filter((entry): entry is ConversationEntry => entry.role === "user" || entry.role === "assistant")
        .map((entry) => ({ role: entry.role, content: entry.content }));

      const controller = new AbortController();
      abortControllerRef.current?.abort();
      abortControllerRef.current = controller;

      try {
        const preferencesPayload: ChatSessionPreferencesPayload = {
          mode: mode.id,
          defaultFilters: defaultFilters ?? null,
          frequentlyOpenedPanels,
        };
        const result = await clientRef.current.runChatWorkflow(
          {
            messages: historyMessages,
            modeId: mode.id,
            sessionId,
            prompt: trimmed,
            filters: defaultFilters ?? null,
            preferences: preferencesPayload,
          },
          {
            signal: controller.signal,
            onEvent: (event) => applyStreamEvent(assistantId, event),
          },
        );

        if (result.kind === "success") {
          setSessionId(result.sessionId);
          updateAssistantEntry(assistantId, (entry) => ({
            ...entry,
            content: result.answer.summary,
            citations: result.answer.citations ?? [],
          }));
        } else if (result.kind === "guardrail") {
          removeEntryById(assistantId);
          setGuardrail({
            message: result.message,
            traceId: result.traceId ?? null,
            suggestions: result.suggestions ?? [],
            metadata: result.metadata ?? null,
          });
        }
      } catch (error) {
        removeEntryById(assistantId);
        if (error instanceof TheoApiError && error.status === 400) {
          const suggestions = buildFallbackSuggestions(trimmed);
          setGuardrail({
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
          });
          setErrorMessage(null);
        } else {
          const message =
            error instanceof Error ? error.message : "We couldn’t complete that chat request.";
          setErrorMessage(message);
        }
      } finally {
        setIsStreaming(false);
        setActiveAssistantId((current) => (current === assistantId ? null : current));
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
      }
    },
    [
      applyStreamEvent,
      buildFallbackSuggestions,
      defaultFilters,
      frequentlyOpenedPanels,
      mode.id,
      removeEntryById,
      sessionId,
      updateAssistantEntry,
    ],
  );

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      await executeChat(inputValue);
    },
    [executeChat, inputValue],
  );

  useEffect(() => {
    if (!autoSubmit || !initialPrompt || autoSubmitRef.current || isRestoring) {
      return;
    }
    autoSubmitRef.current = true;
    void executeChat(initialPrompt);
  }, [autoSubmit, executeChat, initialPrompt, isRestoring]);

  const hasTranscript = conversation.length > 0;

  const transcript = useMemo(() => {
    return conversation.map((entry) => {
      if (entry.role === "assistant") {
        const isActive = entry.id === activeAssistantId && isStreaming;
        const content = entry.content.trim();
        return {
          ...entry,
          displayContent: content || (isActive ? "Generating response…" : ""),
          isActive,
        };
      }
      return { ...entry, displayContent: entry.content, isActive: false };
    });
  }, [activeAssistantId, conversation, isStreaming]);

  const handleRetry = useCallback(() => {
    if (lastQuestion) {
      setInputValue(lastQuestion);
    }
    setGuardrail(null);
  }, [lastQuestion]);

  const guardrailActions: Partial<Pick<ErrorCalloutProps, "onRetry" | "actions">> = {};
  if (lastQuestion) {
    guardrailActions.onRetry = handleRetry;
  }
  if (guardrail && guardrail.suggestions.length) {
    guardrailActions.actions = (
      <div className="guardrail-actions" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {guardrail.suggestions.map((suggestion, index) => (
          <button
            key={`${suggestion.action}-${index}-${suggestion.label}`}
            type="button"
            onClick={() => {
              handleGuardrailSuggestion(suggestion);
              setGuardrail(null);
            }}
          >
            {suggestion.label}
          </button>
        ))}
      </div>
    );
  }

  const handleResetSession = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setConversation([]);
    setSessionId(null);
    setGuardrail(null);
    setErrorMessage(null);
    setLastQuestion(null);
    setIsStreaming(false);
    setDefaultFilters(null);
    setFrequentlyOpenedPanels([]);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
    }
  }, []);

  const handleForkSession = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
    }
    setSessionId(null);
  }, []);

  return (
    <div className="chat-workspace" aria-live="polite">
      <div className="chat-intro">
        <h2>Ask with {mode.label} stance</h2>
        <p>
          We’ll keep the conversation aligned to <strong>{mode.label.toLowerCase()}</strong> emphasis while grounding
          every answer with citations you can inspect.
        </p>
      </div>

      <div className="chat-transcript" role="log" aria-label="Chat transcript">
        {hasTranscript ? (
          transcript.map((entry) => (
            <article key={entry.id} className={`chat-message chat-message--${entry.role}`}>
              <header>{entry.role === "user" ? "You" : "Theo"}</header>
              <p aria-live={entry.isActive ? "polite" : undefined}>{entry.displayContent || "Awaiting response."}</p>
              {entry.role === "assistant" && entry.citations.length > 0 && (
                <aside className="chat-citations" aria-label="Citations">
                  <h4>Citations</h4>
                  <ol>
                    {entry.citations.map((citation) => {
                      const verseHref = `/verse/${encodeURIComponent(citation.osis)}`;
                      const searchParams = new URLSearchParams({ osis: citation.osis });
                      const searchHref = `/search?${searchParams.toString()}`;
                      return (
                        <li key={`${entry.id}-${citation.index}`} className="chat-citation-item">
                          <div>
                            <p className="chat-citation-heading">{citation.osis}</p>
                            <p className="chat-citation-snippet">“{citation.snippet}”</p>
                            {citation.document_title && (
                              <p className="chat-citation-source">{citation.document_title}</p>
                            )}
                          </div>
                          <div className="chat-citation-actions">
                            <Link href={verseHref}>Open {citation.anchor}</Link>
                            <Link href={searchHref}>Search references</Link>
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                </aside>
              )}
            </article>
          ))
        ) : (
          <div className="chat-empty-state">
            <h3>Start the conversation</h3>
            <p>Ask about a passage, doctrine, or theme and we’ll respond with cited insights.</p>
          </div>
        )}
      </div>

      <div className="chat-session-controls" aria-label="Session history controls">
        <button
          type="button"
          onClick={handleResetSession}
          disabled={!hasTranscript || isStreaming || isRestoring}
        >
          Reset session
        </button>
        <button
          type="button"
          onClick={handleForkSession}
          disabled={!hasTranscript || isStreaming || isRestoring}
        >
          Fork conversation
        </button>
      </div>

      {guardrail ? (
        <ErrorCallout
          message={guardrail.message}
          traceId={guardrail.traceId}
          {...guardrailActions}
          retryLabel="Rephrase question"
        />
      ) : null}

      {errorMessage ? <ErrorCallout message={errorMessage} /> : null}

      <form className="chat-form" onSubmit={handleSubmit} aria-label="Chat input">
        <label htmlFor="chat-question">Ask Theo Engine</label>
        <textarea
          id="chat-question"
          name="question"
          required
          rows={4}
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="How does John 1:1 connect with Genesis 1?"
          disabled={isStreaming || isRestoring}
        />
        <div className="chat-form-actions">
          <button type="submit" disabled={!inputValue.trim() || isStreaming || isRestoring}>
            {isStreaming ? "Generating…" : "Send"}
          </button>
        </div>
      </form>
      <p className="chat-footnote">Responses cite the passages and sources that shaped the answer.</p>
    </div>
  );
}
