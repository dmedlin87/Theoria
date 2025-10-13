"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  FileText,
  Globe,
  Search,
  Upload as UploadIcon,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import ErrorCallout, { type ErrorCalloutProps } from "../components/ErrorCallout";
import { Icon } from "../components/Icon";
import type { ChatWorkflowClient } from "../lib/chat-client";
import { createTheoApiClient, TheoApiError } from "../lib/api-client";
import type {
  HybridSearchFilters,
  ChatSessionState,
  ChatWorkflowStreamEvent,
  ChatWorkflowMessage,
  ChatSessionPreferencesPayload,
} from "../lib/api-client";
import {
  type GuardrailSuggestion,
  useGuardrailActions,
} from "../lib/guardrails";
import { useMode } from "../mode-context";
import { emitTelemetry, submitFeedback } from "../lib/telemetry";
import {
  type Reaction,
  type ConversationEntry,
  type AssistantConversationEntry,
  type GuardrailState,
} from "./useChatWorkspaceState";
import type { ChatSessionMemoryEntry } from "../lib/api-client";
import { SessionControls } from "./components/SessionControls";
import { ChatTranscript, type TranscriptEntry } from "./components/transcript/ChatTranscript";
import { useChatSessionState } from "./hooks/useChatSessionState";

import styles from "./ChatWorkspace.module.css";

function classNames(
  ...classes: Array<string | false | null | undefined>
): string {
  return classes.filter(Boolean).join(" ");
}

type ChatWorkspaceProps = {
  client?: ChatWorkflowClient;
  initialPrompt?: string;
  autoSubmit?: boolean;
};

const CHAT_SESSION_STORAGE_KEY = "theo.chat.lastSessionId";

function createMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

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

  const {
    state: {
      conversation,
      feedbackSelections,
      pendingFeedbackIds,
      sessionId,
      isRestoring,
      frequentlyOpenedPanels,
      defaultFilters,
      isStreaming,
      activeAssistantId,
      guardrail,
      errorMessage,
      lastQuestion,
    },
    setters: {
      setConversation,
      setFeedbackSelections,
      setPendingFeedbackIds,
      setSessionId,
      setIsRestoring,
      setFrequentlyOpenedPanels,
      setDefaultFilters,
      setIsStreaming,
      setActiveAssistantId,
      setGuardrail,
      setErrorMessage,
      setLastQuestion,
    },
    selectors: { hasTranscript },
  } = useChatSessionState();
  const conversationRef = useRef<ConversationEntry[]>(conversation);
  useEffect(() => {
    conversationRef.current = conversation;
  }, [conversation]);

  const [inputValue, setInputValue] = useState(initialPrompt ?? "");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  useEffect(() => {
    if (typeof initialPrompt === "string") {
      setInputValue(initialPrompt);
    }
  }, [initialPrompt]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const autoSubmitRef = useRef(false);

  useEffect(() => {
    autoSubmitRef.current = false;
  }, [initialPrompt]);

  const sampleQuestions = useMemo(
    () => [
      "How does John 1:1 connect with Genesis 1?",
      "What does Romans 8 teach about life in the Spirit?",
      "Summarize the Beatitudes in Matthew 5.",
      "Where else does Scripture describe the New Covenant?",
    ],
    [],
  );

  const handleSampleQuestionClick = (prompt: string, index: number) => {
    setInputValue(prompt);
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.focus();
      const caret = prompt.length;
      textarea.setSelectionRange(caret, caret);
    }
    void emitTelemetry(
      [
        {
          event: "chat.sample_question_click",
          durationMs: 0,
          metadata: { index, prompt },
        },
      ],
      { page: "chat" },
    );
  };

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
        state.memory.forEach((entry: ChatSessionMemoryEntry) => {
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
            prompt: entry.question,
          });
        });
        if (restoredConversation.length > 0) {
          const lastUser = restoredConversation
            .slice()
            .reverse()
            .find((entry) => entry.role === "user");
          setLastQuestion(lastUser?.content ?? null);
        }
        setFeedbackSelections({});
        setPendingFeedbackIds(new Set());
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
    setFeedbackSelections((previous) => {
      if (!(id in previous)) {
        return previous;
      }
      const next = { ...previous };
      delete next[id];
      return next;
    });
    setPendingFeedbackIds((previous) => {
      if (!previous.has(id)) {
        return previous;
      }
      const next = new Set(previous);
      next.delete(id);
      return next;
    });
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
        description: "Add material covering this topic so Theoria has grounded sources next time.",
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
        prompt: trimmed,
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
      } catch (error: unknown) {
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

  const transcript = useMemo<TranscriptEntry[]>(() => {
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

  const handleAssistantFeedback = useCallback(
    async (entryId: string, action: Reaction) => {
      if (pendingFeedbackIds.has(entryId)) {
        return;
      }
      setPendingFeedbackIds((previous) => {
        const next = new Set(previous);
        next.add(entryId);
        return next;
      });
      const entry = conversationRef.current.find(
        (candidate): candidate is AssistantConversationEntry =>
          candidate.id === entryId && candidate.role === "assistant",
      );
      try {
        await submitFeedback({
          action,
          chatSessionId: sessionId ?? null,
          query: entry?.prompt ?? entry?.content ?? lastQuestion ?? null,
        });
        setFeedbackSelections((previous) => ({ ...previous, [entryId]: action }));
      } catch (error) {
        if (process.env.NODE_ENV !== "production") {
          console.debug("Failed to submit chat feedback", error);
        }
      } finally {
        setPendingFeedbackIds((previous) => {
          if (!previous.has(entryId)) {
            return previous;
          }
          const next = new Set(previous);
          next.delete(entryId);
          return next;
        });
      }
    },
    [lastQuestion, pendingFeedbackIds, sessionId],
  );

  const guardrailActions: Partial<Pick<ErrorCalloutProps, "onRetry" | "actions">> = {};
  if (lastQuestion) {
    guardrailActions.onRetry = handleRetry;
  }
  if (guardrail && guardrail.suggestions.length) {
    guardrailActions.actions = (
      <div className="guardrail-actions">
        {guardrail.suggestions.map((suggestion: GuardrailSuggestion, index: number) => (
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
    setFeedbackSelections({});
    setPendingFeedbackIds(new Set());
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
    <div className={styles.workspace} aria-live="polite">
      <section className={styles.hero} aria-label="Chat overview">
        <div className={styles.heroContent}>
          <p className={styles.heroEyebrow}>Theoria Copilot</p>
          <h2>Ask with {mode.label} stance</h2>
          <p>
            We’ll keep the conversation aligned to <strong>{mode.label.toLowerCase()}</strong> emphasis while grounding
            every answer with citations you can inspect. Follow threads, branch ideas, and stay rooted in scripture.
          </p>
          <div className={styles.heroActions} aria-label="Quick navigation">
            <Link href="/search" className={styles.heroAction}>
              <span className={styles.heroActionIcon}>
                <Icon icon={Search} size="lg" />
              </span>
              <span className={styles.heroActionCopy}>
                <strong>Search the library</strong>
                <span>Jump into cross-references</span>
              </span>
              <span className={styles.heroActionArrow}>
                <Icon icon={ArrowRight} size="md" />
              </span>
            </Link>
            <Link href="/verse" className={styles.heroAction}>
              <span className={styles.heroActionIcon}>
                <Icon icon={BookOpen} size="lg" />
              </span>
              <span className={styles.heroActionCopy}>
                <strong>Trace a passage</strong>
                <span>Explore every verse connection</span>
              </span>
              <span className={styles.heroActionArrow}>
                <Icon icon={ArrowRight} size="md" />
              </span>
            </Link>
            <Link href="/upload" className={styles.heroAction}>
              <span className={styles.heroActionIcon}>
                <Icon icon={UploadIcon} size="lg" />
              </span>
              <span className={styles.heroActionCopy}>
                <strong>Enrich your corpus</strong>
                <span>Upload documents for future chats</span>
              </span>
              <span className={styles.heroActionArrow}>
                <Icon icon={ArrowRight} size="md" />
              </span>
            </Link>
          </div>
        </div>
        <ul className={styles.heroHighlights} aria-label="What this workspace offers">
          <li className={styles.heroHighlight}>
            <span className={styles.heroHighlightIcon}>
              <Icon icon={CheckCircle} size="lg" />
            </span>
            <div>
              <p className={styles.heroHighlightTitle}>Grounded answers</p>
              <p className={styles.heroHighlightText}>Every response links back to trusted sources.</p>
            </div>
          </li>
          <li className={styles.heroHighlight}>
            <span className={styles.heroHighlightIcon}>
              <Icon icon={Globe} size="lg" />
            </span>
            <div>
              <p className={styles.heroHighlightTitle}>Perspective aware</p>
              <p className={styles.heroHighlightText}>Tune the stance to match your research context.</p>
            </div>
          </li>
          <li className={styles.heroHighlight}>
            <span className={styles.heroHighlightIcon}>
              <Icon icon={FileText} size="lg" />
            </span>
            <div>
              <p className={styles.heroHighlightTitle}>Export ready</p>
              <p className={styles.heroHighlightText}>Capture threads and build shareable briefs effortlessly.</p>
            </div>
          </li>
        </ul>
      </section>

      <div className={styles.transcript} role="log" aria-label="Chat transcript">
        {hasTranscript ? (
          transcript.map((entry) => {
            const selection = feedbackSelections[entry.id] ?? null;
            const feedbackPending = pendingFeedbackIds.has(entry.id);
            const feedbackDisabled = feedbackPending || entry.isActive;
            const messageClass = classNames(
              styles.message,
              entry.role === "user" ? styles.messageUser : styles.messageAssistant,
            );
            return (
              <article key={entry.id} className={messageClass}>
                <header>{entry.role === "user" ? "You" : "Theo"}</header>
                <p aria-live={entry.isActive ? "polite" : undefined}>{entry.displayContent || "Awaiting response."}</p>
                {entry.role === "assistant" && entry.citations.length > 0 && (
                  <aside className={styles.citations} aria-label="Citations">
                    <h4>Citations</h4>
                    <ol>
                      {entry.citations.map((citation) => {
                      const verseHref = `/verse/${encodeURIComponent(citation.osis)}`;
                      const searchParams = new URLSearchParams({ osis: citation.osis });
                      const searchHref = `/search?${searchParams.toString()}`;
                      return (
                        <li key={`${entry.id}-${citation.index}`} className={styles.citationItem}>
                          <div>
                            <p className={styles.citationHeading}>{citation.osis}</p>
                            <p className={styles.citationSnippet}>“{citation.snippet}”</p>
                            {citation.document_title && (
                              <p className={styles.citationSource}>{citation.document_title}</p>
                            )}
                          </div>
                          <div className={styles.citationActions}>
                            <Link href={verseHref}>Open {citation.anchor}</Link>
                            <Link href={searchHref}>Search references</Link>
                          </div>
                        </li>
                      );
                      })}
                    </ol>
                  </aside>
                )}
                {entry.role === "assistant" && (
                  <div className={styles.feedbackControls}>
                    <button
                      type="button"
                      className={classNames(
                        styles.feedbackButton,
                        styles.feedbackButtonPositive,
                        selection === "like" && styles.feedbackButtonActive,
                      )}
                      onClick={() => handleAssistantFeedback(entry.id, "like")}
                      disabled={feedbackDisabled}
                      aria-pressed={selection === "like"}
                      aria-label="Mark response helpful"
                    >
                      <Icon icon={ThumbsUp} size="md" />
                      <span className="visually-hidden">Helpful response</span>
                    </button>
                    <button
                      type="button"
                      className={classNames(
                        styles.feedbackButton,
                        styles.feedbackButtonNegative,
                        selection === "dislike" && styles.feedbackButtonActive,
                      )}
                      onClick={() => handleAssistantFeedback(entry.id, "dislike")}
                      disabled={feedbackDisabled}
                      aria-pressed={selection === "dislike"}
                      aria-label="Mark response unhelpful"
                    >
                      <Icon icon={ThumbsDown} size="md" />
                      <span className="visually-hidden">Unhelpful response</span>
                    </button>
                  </div>
                )}
              </article>
            );
          })
        ) : (
          <div className={styles.emptyState}>
            <h3>Start the conversation</h3>
            <p>Ask about a passage, doctrine, or theme and we’ll respond with cited insights.</p>
            <ul className={styles.emptyStateActions}>
              {sampleQuestions.map((question, index) => (
                <li key={question}>
                  <button
                    type="button"
                    className={styles.emptyStateChip}
                    onClick={() => handleSampleQuestionClick(question, index)}
                  >
                    {question}
                  </button>
                </li>
              ))}
            </ul>
            <p className={styles.emptyStateLinks}>
              Prefer browsing? Explore the <Link href="/search">Search</Link> and
              {" "}
              <Link href="/verse">Verse explorer</Link>.
            </p>
          </div>
        )}
      </div>

      <SessionControls
        disabled={!hasTranscript || isStreaming || isRestoring}
        onReset={handleResetSession}
        onFork={handleForkSession}
      />
      <div className={styles.sessionControls} aria-label="Session history controls">
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

      <form className={styles.form} onSubmit={handleSubmit} aria-label="Chat input">
        <label htmlFor="chat-question">Ask Theoria</label>
        <textarea
          id="chat-question"
          name="question"
          required
          rows={4}
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="How does John 1:1 connect with Genesis 1?"
          disabled={isStreaming || isRestoring}
          ref={textareaRef}
        />
        <div className={styles.formActions}>
          <button type="submit" disabled={!inputValue.trim() || isStreaming || isRestoring}>
            {isStreaming ? "Generating…" : "Send"}
          </button>
        </div>
      </form>
      <p className={styles.footnote}>Responses cite the passages and sources that shaped the answer.</p>
    </div>
  );
}
