"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  FileText,
  Globe,
  Search,
  ThumbsDown,
  ThumbsUp,
  Upload as UploadIcon,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import ErrorCallout, { type ErrorCalloutProps } from "../components/ErrorCallout";
import { Icon } from "../components/Icon";
import type { ChatWorkflowClient } from "../lib/chat-client";
import { createTheoApiClient } from "../lib/api-client";
import type { HybridSearchFilters } from "../lib/guardrails";
import {
  type GuardrailSuggestion,
  useGuardrailActions,
} from "../lib/guardrails";
import { useMode } from "../mode-context";
import { emitTelemetry, submitFeedback, type FeedbackAction } from "../lib/telemetry";
import { useChatWorkspaceState, type Reaction, type AssistantConversationEntry } from "./useChatWorkspaceState";
import { useSessionRestoration, useSessionPersistence, CHAT_SESSION_STORAGE_KEY } from "./useSessionRestoration";
import { useChatExecution } from "./useChatExecution";

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
  const { mode } = useMode();
  const handleGuardrailSuggestion = useGuardrailActions();
  
  // Initialize state management
  const { state, dispatch, actions, computed } = useChatWorkspaceState();
  
  // Setup client
  const [fallbackClient] = useState(() => createTheoApiClient());
  const activeClient = client ?? fallbackClient;
  const clientRef = useRef<ChatWorkflowClient>(activeClient);
  useEffect(() => {
    clientRef.current = activeClient;
  }, [activeClient]);

  // Input management
  const [inputValue, setInputValue] = useState(initialPrompt ?? "");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const autoSubmitRef = useRef(false);

  useEffect(() => {
    if (typeof initialPrompt === "string") {
      setInputValue(initialPrompt);
    }
    autoSubmitRef.current = false;
  }, [initialPrompt]);

  // Sample questions
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

  // Build fallback suggestions for guardrail errors
  const buildFallbackSuggestions = useCallback(
    (questionHint: string | null): GuardrailSuggestion[] => {
      const searchSuggestion: GuardrailSuggestion = {
        action: "search",
        label: "Search related passages",
        description:
          "Open the search workspace to inspect passages that align with your guardrail settings before retrying.",
        query: questionHint ?? null,
        osis: null,
        filters: state.defaultFilters ?? null,
      };
      const uploadSuggestion: GuardrailSuggestion = {
        action: "upload",
        label: "Upload supporting documents",
        description: "Add material covering this topic so Theoria has grounded sources next time.",
        collection: state.defaultFilters?.collection ?? null,
      };
      return [searchSuggestion, uploadSuggestion];
    },
    [state.defaultFilters],
  );

  // Session restoration with retry logic
  useSessionRestoration(
    clientRef,
    dispatch,
    state.restorationAttempts,
    computed.canRetryRestoration
  );

  // Session persistence to localStorage
  useSessionPersistence(state.sessionId);

  // Chat execution with streaming
  const { executeChat, abortCurrentRequest } = useChatExecution(
    clientRef,
    dispatch,
    state.conversation,
    state.sessionId,
    mode.id,
    state.defaultFilters,
    state.frequentlyOpenedPanels,
    buildFallbackSuggestions
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortCurrentRequest();
    };
  }, [abortCurrentRequest]);

  // Auto-submit handling
  useEffect(() => {
    if (!autoSubmit || !initialPrompt || autoSubmitRef.current || state.isRestoring) {
      return;
    }
    autoSubmitRef.current = true;
    void executeChat(initialPrompt);
  }, [autoSubmit, executeChat, initialPrompt, state.isRestoring]);

  // Form submission
  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      await executeChat(inputValue);
      setInputValue("");
    },
    [executeChat, inputValue],
  );

  // Prepare transcript with display formatting
  const transcript = useMemo(() => {
    return state.conversation.map((entry) => {
      if (entry.role === "assistant") {
        const isActive = entry.id === state.activeAssistantId && state.isStreaming;
        const content = entry.content.trim();
        return {
          ...entry,
          displayContent: content || (isActive ? "Generating response…" : ""),
          isActive,
        };
      }
      return { ...entry, displayContent: entry.content, isActive: false };
    });
  }, [state.activeAssistantId, state.conversation, state.isStreaming]);

  // Feedback handling
  const handleAssistantFeedback = useCallback(
    async (entryId: string, action: Reaction) => {
      if (state.pendingFeedbackIds.has(entryId)) {
        return;
      }
      
      actions.setFeedbackPending(entryId, true);
      
      const entry = state.conversation.find(
        (candidate): candidate is AssistantConversationEntry =>
          candidate.id === entryId && candidate.role === "assistant",
      );
      
      try {
        await submitFeedback({
          action,
          chatSessionId: state.sessionId ?? null,
          query: entry?.prompt ?? entry?.content ?? state.lastQuestion ?? null,
        });
        actions.setFeedbackSelection(entryId, action);
      } catch (error) {
        if (process.env.NODE_ENV !== "production") {
          console.debug("Failed to submit chat feedback", error);
        }
      } finally {
        actions.setFeedbackPending(entryId, false);
      }
    },
    [actions, state.conversation, state.lastQuestion, state.pendingFeedbackIds, state.sessionId],
  );

  // Retry handler for guardrails
  const handleRetry = useCallback(() => {
    if (state.lastQuestion) {
      setInputValue(state.lastQuestion);
    }
    actions.clearGuardrail();
  }, [state.lastQuestion, actions]);

  // Session management
  const handleResetSession = useCallback(() => {
    abortCurrentRequest();
    dispatch({ type: "RESET_SESSION" });
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
    }
  }, [abortCurrentRequest, dispatch]);

  const handleForkSession = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
    }
    dispatch({ type: "FORK_SESSION" });
  }, [dispatch]);

  // Guardrail actions
  const guardrailActions: Partial<Pick<ErrorCalloutProps, "onRetry" | "actions">> = {};
  if (state.lastQuestion) {
    guardrailActions.onRetry = handleRetry;
  }
  if (state.guardrail && state.guardrail.suggestions.length) {
    guardrailActions.actions = (
      <div className="guardrail-actions">
        {state.guardrail.suggestions.map((suggestion, index) => (
          <button
            key={`${suggestion.action}-${index}-${suggestion.label}`}
            type="button"
            onClick={() => {
              handleGuardrailSuggestion(suggestion);
              actions.clearGuardrail();
            }}
          >
            {suggestion.label}
          </button>
        ))}
      </div>
    );
  }

  // Show restoration status
  const showRestorationIndicator = state.restorationStatus === "loading" || state.restorationStatus === "retrying";

  return (
    <div className="chat-workspace" aria-live="polite">
      <section className="chat-hero" aria-label="Chat overview">
        <div className="chat-hero__content">
          <p className="chat-hero__eyebrow">Theoria Copilot</p>
          <h2>Ask with {mode.label} stance</h2>
          <p>
            We'll keep the conversation aligned to <strong>{mode.label.toLowerCase()}</strong> emphasis while grounding
            every answer with citations you can inspect. Follow threads, branch ideas, and stay rooted in scripture.
          </p>
        <div className="chat-hero__actions" aria-label="Quick navigation">
          <Link href="/search" className="chat-hero__action">
            <span className="chat-hero__action-icon">
              <Icon icon={Search} size="lg" />
            </span>
            <span className="chat-hero__action-copy">
              <strong>Search the library</strong>
              <span>Jump into cross-references</span>
            </span>
            <span className="chat-hero__action-arrow">
              <Icon icon={ArrowRight} size="md" />
            </span>
          </Link>
          <Link href="/verse" className="chat-hero__action">
            <span className="chat-hero__action-icon">
              <Icon icon={BookOpen} size="lg" />
            </span>
            <span className="chat-hero__action-copy">
              <strong>Trace a passage</strong>
              <span>Explore every verse connection</span>
            </span>
            <span className="chat-hero__action-arrow">
              <Icon icon={ArrowRight} size="md" />
            </span>
          </Link>
          <Link href="/upload" className="chat-hero__action">
            <span className="chat-hero__action-icon">
              <Icon icon={UploadIcon} size="lg" />
            </span>
            <span className="chat-hero__action-copy">
              <strong>Enrich your corpus</strong>
              <span>Upload documents for future chats</span>
            </span>
            <span className="chat-hero__action-arrow">
              <Icon icon={ArrowRight} size="md" />
            </span>
          </Link>
        </div>
        </div>
        <ul className="chat-hero__highlights" aria-label="What this workspace offers">
          <li className="chat-hero__highlight">
            <span className="chat-hero__highlight-icon">
              <Icon icon={CheckCircle} size="lg" />
            </span>
            <div>
              <p className="chat-hero__highlight-title">Grounded answers</p>
              <p className="chat-hero__highlight-text">Every response links back to trusted sources.</p>
            </div>
          </li>
          <li className="chat-hero__highlight">
            <span className="chat-hero__highlight-icon">
              <Icon icon={Globe} size="lg" />
            </span>
            <div>
              <p className="chat-hero__highlight-title">Perspective aware</p>
              <p className="chat-hero__highlight-text">Tune the stance to match your research context.</p>
            </div>
          </li>
          <li className="chat-hero__highlight">
            <span className="chat-hero__highlight-icon">
              <Icon icon={FileText} size="lg" />
            </span>
            <div>
              <p className="chat-hero__highlight-title">Export ready</p>
              <p className="chat-hero__highlight-text">Capture threads and build shareable briefs effortlessly.</p>
            </div>
          </li>
        </ul>
      </section>

      {showRestorationIndicator && (
        <div className="chat-restoration-indicator" role="status">
          <p>
            {state.restorationStatus === "loading" && "Restoring previous conversation..."}
            {state.restorationStatus === "retrying" && `Retrying session restoration (attempt ${state.restorationAttempts + 1})...`}
          </p>
        </div>
      )}

      <div className="chat-transcript" role="log" aria-label="Chat transcript">
        {computed.hasTranscript ? (
          transcript.map((entry) => {
            const selection = state.feedbackSelections[entry.id] ?? null;
            const feedbackPending = state.pendingFeedbackIds.has(entry.id);
            const feedbackDisabled = feedbackPending || entry.isActive;
            return (
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
                            <p className="chat-citation-snippet">"{citation.snippet}"</p>
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
                {entry.role === "assistant" && (
                  <div className="chat-feedback-controls">
                    <button
                      type="button"
                      className={`chat-feedback-button chat-feedback-button--positive${
                        selection === "like" ? " chat-feedback-button--active" : ""
                      }`}
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
                      className={`chat-feedback-button chat-feedback-button--negative${
                        selection === "dislike" ? " chat-feedback-button--active" : ""
                      }`}
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
          <div className="chat-empty-state">
            <h3>Start the conversation</h3>
            <p>Ask about a passage, doctrine, or theme and we'll respond with cited insights.</p>
            <ul className="chat-empty-state-actions">
              {sampleQuestions.map((question, index) => (
                <li key={question}>
                  <button
                    type="button"
                    className="chat-empty-state-chip"
                    onClick={() => handleSampleQuestionClick(question, index)}
                  >
                    {question}
                  </button>
                </li>
              ))}
            </ul>
            <p className="chat-empty-state-links">
              Prefer browsing? Explore the <Link href="/search">Search</Link> and
              {" "}
              <Link href="/verse">Verse explorer</Link>.
            </p>
          </div>
        )}
      </div>

      <div className="chat-session-controls" aria-label="Session history controls">
        <button
          type="button"
          onClick={handleResetSession}
          disabled={!computed.hasTranscript || state.isStreaming || state.isRestoring}
        >
          Reset session
        </button>
        <button
          type="button"
          onClick={handleForkSession}
          disabled={!computed.hasTranscript || state.isStreaming || state.isRestoring}
        >
          Fork conversation
        </button>
      </div>

      {state.guardrail ? (
        <ErrorCallout
          message={state.guardrail.message}
          traceId={state.guardrail.traceId}
          {...guardrailActions}
          retryLabel="Rephrase question"
        />
      ) : null}

      {state.errorMessage ? <ErrorCallout message={state.errorMessage} /> : null}

      <form className="chat-form" onSubmit={handleSubmit} aria-label="Chat input">
        <label htmlFor="chat-question">Ask Theoria</label>
        <textarea
          id="chat-question"
          name="question"
          required
          rows={4}
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="How does John 1:1 connect with Genesis 1?"
          disabled={state.isStreaming || state.isRestoring}
          ref={textareaRef}
        />
        <div className="chat-form-actions">
          <button type="submit" disabled={!inputValue.trim() || state.isStreaming || state.isRestoring}>
            {state.isStreaming ? "Generating…" : "Send"}
          </button>
        </div>
      </form>
      <p className="chat-footnote">Responses cite the passages and sources that shaped the answer.</p>
    </div>
  );
}
