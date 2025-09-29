"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import ErrorCallout, { type ErrorCalloutProps } from "../components/ErrorCallout";
import type {
  ChatSessionDetails,
  ChatWorkflowClient,
  ChatWorkflowMessage,
  ChatWorkflowStreamEvent,
} from "../lib/api-client";
import { createTheoApiClient } from "../lib/api-client";
import type { RAGCitation } from "../copilot/components/types";
import { isResearchModeId } from "../mode-config";
import { useMode } from "../mode-context";

const CHAT_SESSION_STORAGE_KEY = "theo.chat.sessions";
const MAX_STORED_SESSIONS = 5;
const MEMORY_SNIPPET_LIMIT = 12;
const MEMORY_SNIPPET_LENGTH = 320;

function clampMemorySnippets(snippets: string[]): string[] {
  const windowSize = Math.max(MEMORY_SNIPPET_LIMIT * 2, MEMORY_SNIPPET_LIMIT);
  const trimmed: string[] = [];
  for (const snippet of snippets.slice(-windowSize)) {
    const text = snippet.trim();
    if (!text) {
      continue;
    }
    trimmed.push(text.slice(0, MEMORY_SNIPPET_LENGTH));
  }
  if (trimmed.length > MEMORY_SNIPPET_LIMIT) {
    return trimmed.slice(-MEMORY_SNIPPET_LIMIT);
  }
  return trimmed;
}

function loadStoredSessions(): string[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(CHAT_SESSION_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    const result: string[] = [];
    for (const item of parsed) {
      if (typeof item !== "string") {
        continue;
      }
      const trimmed = item.trim();
      if (!trimmed || result.includes(trimmed)) {
        continue;
      }
      result.push(trimmed);
    }
    return result;
  } catch {
    return [];
  }
}

function storeSessions(ids: string[]): void {
  if (typeof window === "undefined") {
    return;
  }
  if (!ids.length) {
    window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(CHAT_SESSION_STORAGE_KEY, JSON.stringify(ids));
}

function formatSessionLabel(id: string, index: number): string {
  const suffix = id.slice(-6);
  return `Session ${index + 1} (${suffix})`;
}

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

type GuardrailState = { message: string; traceId: string | null } | null;

type ChatWorkspaceProps = {
  client?: ChatWorkflowClient;
  initialPrompt?: string;
  autoSubmit?: boolean;
};

export default function ChatWorkspace({
  client,
  initialPrompt,
  autoSubmit = false,
}: ChatWorkspaceProps): JSX.Element {
  const { mode, setMode } = useMode();
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
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeAssistantId, setActiveAssistantId] = useState<string | null>(null);
  const [guardrail, setGuardrail] = useState<GuardrailState>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [recentSessions, setRecentSessions] = useState<string[]>([]);
  const [sessionSummary, setSessionSummary] = useState<string | null>(null);
  const [memorySnippets, setMemorySnippets] = useState<string[]>([]);
  const memoryRef = useRef<string[]>(memorySnippets);
  useEffect(() => {
    memoryRef.current = memorySnippets;
  }, [memorySnippets]);
  const [frequentlyOpenedPanels, setFrequentlyOpenedPanels] = useState<string[]>([]);
  const panelsRef = useRef<string[]>(frequentlyOpenedPanels);
  useEffect(() => {
    panelsRef.current = frequentlyOpenedPanels;
  }, [frequentlyOpenedPanels]);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const lastQuestionRef = useRef<string | null>(lastQuestion);
  useEffect(() => {
    lastQuestionRef.current = lastQuestion;
  }, [lastQuestion]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const autoSubmitRef = useRef(false);
  const memoryUpdatedRef = useRef(false);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const updateStoredSessions = useCallback((transform: (ids: string[]) => string[]) => {
    setRecentSessions((current) => {
      const next = transform(current);
      const limited = next.slice(0, MAX_STORED_SESSIONS);
      storeSessions(limited);
      return limited;
    });
  }, []);

  const appendMemory = useCallback(
    (questionText: string, answerSummary: string) => {
      const snippets = [...memoryRef.current];
      const trimmedQuestion = questionText.trim();
      const trimmedAnswer = answerSummary.trim();
      if (trimmedQuestion) {
        snippets.push(`User: ${trimmedQuestion}`);
      }
      if (trimmedAnswer) {
        snippets.push(`Theo: ${trimmedAnswer}`);
      }
      setMemorySnippets(clampMemorySnippets(snippets));
    },
    [setMemorySnippets],
  );

  const applySessionDetails = useCallback(
    (details: ChatSessionDetails) => {
      setSessionId(details.sessionId);
      const summary = details.summary ?? details.memory.summary ?? null;
      setSessionSummary(summary);
      setMemorySnippets(clampMemorySnippets(details.memory.snippets ?? []));
      setFrequentlyOpenedPanels(details.preferences.frequentlyOpenedPanels ?? []);
      const restoredConversation: ConversationEntry[] = details.messages.map((entry) =>
        entry.role === "assistant"
          ? {
              id: entry.id,
              role: "assistant",
              content: entry.content,
              citations: entry.citations ?? [],
            }
          : { id: entry.id, role: "user", content: entry.content },
      );
      setConversation(restoredConversation);
      setGuardrail(null);
      setErrorMessage(null);
      setActiveAssistantId(null);
      setIsStreaming(false);
      setLastQuestion(null);
      lastQuestionRef.current = null;
      memoryUpdatedRef.current = false;
      setInputValue("");
      if (
        details.preferences.modeId &&
        details.preferences.modeId !== mode.id &&
        isResearchModeId(details.preferences.modeId)
      ) {
        setMode(details.preferences.modeId);
      }
    },
    [mode.id, setConversation, setErrorMessage, setGuardrail, setIsStreaming, setMemorySnippets, setMode, setSessionSummary, setFrequentlyOpenedPanels],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const stored = loadStoredSessions();
    if (stored.length) {
      setRecentSessions(stored.slice(0, MAX_STORED_SESSIONS));
    }
    if (!stored.length) {
      return;
    }
    let cancelled = false;
    const hydrate = async () => {
      for (const sessionKey of stored) {
        try {
          const details = await clientRef.current.getChatSession(sessionKey);
          if (cancelled) {
            return;
          }
          if (!details) {
            updateStoredSessions((current) => current.filter((id) => id !== sessionKey));
            continue;
          }
          applySessionDetails(details);
          updateStoredSessions((current) => {
            const without = current.filter((id) => id !== details.sessionId);
            return [details.sessionId, ...without];
          });
          break;
        } catch (error) {
          if (!cancelled) {
            updateStoredSessions((current) => current.filter((id) => id !== sessionKey));
            setErrorMessage((previous) => previous ?? "We couldn’t restore the last conversation.");
          }
        }
      }
    };
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [applySessionDetails, updateStoredSessions]);

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
        });
        setActiveAssistantId(null);
        setIsStreaming(false);
        abortControllerRef.current?.abort();
        abortControllerRef.current = null;
        return;
      }
      if (event.type === "complete") {
        setSessionId(event.response.sessionId);
        updateStoredSessions((current) => {
          const without = current.filter((id) => id !== event.response.sessionId);
          return [event.response.sessionId, ...without];
        });
        const summaryText = event.response.answer.summary ?? "";
        setSessionSummary(summaryText || null);
        appendMemory(lastQuestionRef.current ?? "", summaryText);
        memoryUpdatedRef.current = true;
        updateAssistantEntry(assistantId, (entry) => ({
          ...entry,
          content: event.response.answer.summary,
          citations: event.response.answer.citations ?? [],
        }));
        setActiveAssistantId(null);
        return;
      }
    },
    [appendMemory, removeEntryById, updateAssistantEntry, updateStoredSessions],
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
      lastQuestionRef.current = trimmed;
      setInputValue("");
      setIsStreaming(true);

      const historyMessages: ChatWorkflowMessage[] = [...baseConversation, userEntry]
        .filter((entry): entry is ConversationEntry => entry.role === "user" || entry.role === "assistant")
        .map((entry) => ({ role: entry.role, content: entry.content }));

      const controller = new AbortController();
      abortControllerRef.current?.abort();
      abortControllerRef.current = controller;
      memoryUpdatedRef.current = false;

      try {
        const result = await clientRef.current.runChatWorkflow(
          {
            messages: historyMessages,
            modeId: mode.id,
            sessionId,
            prompt: trimmed,
            frequentlyOpenedPanels: panelsRef.current,
          },
          {
            signal: controller.signal,
            onEvent: (event) => applyStreamEvent(assistantId, event),
          },
        );

        if (result.kind === "success") {
          setSessionId(result.sessionId);
          updateStoredSessions((current) => {
            const without = current.filter((id) => id !== result.sessionId);
            return [result.sessionId, ...without];
          });
          updateAssistantEntry(assistantId, (entry) => ({
            ...entry,
            content: result.answer.summary,
            citations: result.answer.citations ?? [],
          }));
          const summaryText = result.answer.summary ?? "";
          setSessionSummary(summaryText || null);
          if (!memoryUpdatedRef.current) {
            appendMemory(trimmed, summaryText);
          }
          memoryUpdatedRef.current = false;
        } else if (result.kind === "guardrail") {
          removeEntryById(assistantId);
          setGuardrail({ message: result.message, traceId: result.traceId ?? null });
        }
      } catch (error) {
        removeEntryById(assistantId);
        const message =
          error instanceof Error ? error.message : "We couldn’t complete that chat request.";
        setErrorMessage(message);
      } finally {
        setIsStreaming(false);
        setActiveAssistantId((current) => (current === assistantId ? null : current));
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
        memoryUpdatedRef.current = false;
      }
    },
    [appendMemory, applyStreamEvent, mode.id, removeEntryById, sessionId, updateAssistantEntry, updateStoredSessions],
  );

  const handleSessionSelect = useCallback(
    async (event: ChangeEvent<HTMLSelectElement>) => {
      const rawValue = event.target.value;
      const selectedId = rawValue.trim();
      if (!selectedId) {
        setSessionId(null);
        setConversation([]);
        setSessionSummary(null);
        setMemorySnippets([]);
        setFrequentlyOpenedPanels([]);
        setGuardrail(null);
        setErrorMessage(null);
        setLastQuestion(null);
        lastQuestionRef.current = null;
        memoryUpdatedRef.current = false;
        setInputValue("");
        return;
      }
      if (selectedId === sessionId) {
        return;
      }
      try {
        const details = await clientRef.current.getChatSession(selectedId);
        if (!details) {
          updateStoredSessions((current) => current.filter((id) => id !== selectedId));
          setErrorMessage("We couldn’t find that conversation.");
          return;
        }
        applySessionDetails(details);
        updateStoredSessions((current) => {
          const without = current.filter((id) => id !== details.sessionId);
          return [details.sessionId, ...without];
        });
      } catch (error) {
        updateStoredSessions((current) => current.filter((id) => id !== selectedId));
        const message =
          error instanceof Error ? error.message : "We couldn’t load that conversation.";
        setErrorMessage(message);
      }
    },
    [applySessionDetails, sessionId, updateStoredSessions],
  );

  const handleReset = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    if (sessionId) {
      updateStoredSessions((current) => current.filter((id) => id !== sessionId));
    }
    setConversation([]);
    setSessionId(null);
    setSessionSummary(null);
    setMemorySnippets([]);
    setFrequentlyOpenedPanels([]);
    setGuardrail(null);
    setErrorMessage(null);
    setLastQuestion(null);
    lastQuestionRef.current = null;
    memoryUpdatedRef.current = false;
    setInputValue("");
  }, [sessionId, updateStoredSessions]);

  const handleFork = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setSessionId(null);
    setGuardrail(null);
    setErrorMessage(null);
    memoryUpdatedRef.current = false;
    setLastQuestion(null);
    lastQuestionRef.current = null;
  }, []);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      await executeChat(inputValue);
    },
    [executeChat, inputValue],
  );

  useEffect(() => {
    if (!autoSubmit || !initialPrompt || autoSubmitRef.current) {
      return;
    }
    autoSubmitRef.current = true;
    void executeChat(initialPrompt);
  }, [autoSubmit, executeChat, initialPrompt]);

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

  const guardrailActions: Partial<Pick<ErrorCalloutProps, "onRetry">> = lastQuestion
    ? { onRetry: handleRetry }
    : {};

  return (
    <div className="chat-workspace" aria-live="polite">
      <div className="chat-intro">
        <h2>Ask with {mode.label} stance</h2>
        <p>
          We’ll keep the conversation aligned to <strong>{mode.label.toLowerCase()}</strong> emphasis while grounding
          every answer with citations you can inspect.
        </p>
      </div>

      <div className="chat-session-controls">
        <div className="chat-session-picker">
          <label htmlFor="chat-session-selector">Recent conversations</label>
          <select
            id="chat-session-selector"
            value={sessionId ?? ""}
            onChange={handleSessionSelect}
          >
            <option value="">Start new conversation</option>
            {recentSessions.map((id, index) => (
              <option key={id} value={id}>
                {formatSessionLabel(id, index)}
              </option>
            ))}
          </select>
        </div>
        <div className="chat-session-actions">
          <button
            type="button"
            onClick={handleReset}
            disabled={!sessionId && conversation.length === 0}
          >
            Reset
          </button>
          <button
            type="button"
            onClick={handleFork}
            disabled={conversation.length === 0}
          >
            Fork
          </button>
        </div>
      </div>

      {(sessionSummary || memorySnippets.length > 0) && (
        <aside className="chat-memory" aria-label="Conversation memory">
          {sessionSummary ? <p className="chat-memory-summary">{sessionSummary}</p> : null}
          {memorySnippets.length > 0 && (
            <ul className="chat-memory-list">
              {memorySnippets.map((snippet, index) => (
                <li key={`memory-${index}`}>{snippet}</li>
              ))}
            </ul>
          )}
        </aside>
      )}

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
          disabled={isStreaming}
        />
        <div className="chat-form-actions">
          <button type="submit" disabled={!inputValue.trim() || isStreaming}>
            {isStreaming ? "Generating…" : "Send"}
          </button>
        </div>
      </form>
      <p className="chat-footnote">Responses cite the passages and sources that shaped the answer.</p>
    </div>
  );
}
