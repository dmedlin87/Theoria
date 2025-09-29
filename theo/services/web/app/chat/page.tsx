"use client";

import {
  FormEvent,
  useCallback,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import ErrorCallout from "../components/ErrorCallout";
import ModeChangeBanner from "../components/ModeChangeBanner";
import { createTheoApiClient } from "../lib/api-client";
import {
  dispatchSuggestionAction,
  extractTraceId,
  suggestionFromError,
  type FailureSuggestion,
} from "../lib/failure-suggestions";
import { useMode } from "../mode-context";
import type { components } from "../lib/generated/api";

type ChatMessage = components["schemas"]["ChatSessionMessage"];

type ErrorState = {
  message: string;
  suggestion: FailureSuggestion | null;
  traceId: string | null;
};

type SearchPrefill = {
  query?: string;
  osis?: string | null;
};

function createUserMessage(content: string): ChatMessage {
  return { role: "user", content } satisfies ChatMessage;
}

export default function ChatPage(): JSX.Element {
  const { mode } = useMode();
  const router = useRouter();
  const apiClient = useMemo(() => createTheoApiClient(), []);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [osis, setOsis] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [errorState, setErrorState] = useState<ErrorState | null>(null);
  const [searchPanelOpen, setSearchPanelOpen] = useState(false);
  const [uploadPanelOpen, setUploadPanelOpen] = useState(false);
  const [searchPrefill, setSearchPrefill] = useState<SearchPrefill>({});
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const clearError = useCallback(() => {
    setErrorState(null);
  }, []);

  const recordError = useCallback(
    (error: unknown, fallbackMessage: string, context: { question: string; osis?: string | null }) => {
      const suggestion = suggestionFromError(error, context);
      const message =
        error instanceof Error && error.message ? error.message : fallbackMessage;
      const traceId = extractTraceId(error);
      setErrorState({
        message,
        suggestion,
        traceId: traceId ?? null,
      });
      if (suggestion?.action.kind === "open-search") {
        setSearchPrefill({
          query: suggestion.action.query ?? context.question,
          osis: suggestion.action.osis ?? context.osis ?? null,
        });
      }
    },
    [],
  );

  const handleSuggestionAction = useCallback(
    (suggestion: FailureSuggestion) => {
      dispatchSuggestionAction(suggestion.action, {
        openSearchPanel: ({ query, osis: osisValue }) => {
          const fallbackQuery = input.trim();
          const resolvedQuery = query ?? searchPrefill.query ?? fallbackQuery || undefined;
          const resolvedOsis =
            osisValue ?? searchPrefill.osis ?? (osis.trim() ? osis.trim() : null);
          setSearchPanelOpen(true);
          setUploadPanelOpen(false);
          setSearchPrefill({ query: resolvedQuery, osis: resolvedOsis });
        },
        openUploadPanel: () => {
          setUploadPanelOpen(true);
          setSearchPanelOpen(false);
        },
        focusInput: () => {
          inputRef.current?.focus();
        },
      });
    },
    [input, osis, searchPrefill],
  );

  const renderSuggestionAction = useCallback(
    (suggestion: FailureSuggestion) => {
      const defaultLabel =
        suggestion.action.label ??
        (suggestion.action.kind === "open-search"
          ? "Open search"
          : suggestion.action.kind === "open-upload"
          ? "Open upload"
          : "Edit prompt");
      return (
        <button
          type="button"
          className="button secondary"
          onClick={() => handleSuggestionAction(suggestion)}
        >
          {defaultLabel}
        </button>
      );
    },
    [handleSuggestionAction],
  );

  const errorCallout = errorState ? (
    <ErrorCallout
      message={errorState.message}
      traceId={errorState.traceId}
      actions={
        errorState.suggestion ? renderSuggestionAction(errorState.suggestion) : undefined
      }
    />
  ) : null;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = input.trim();
    if (!question) {
      recordError(new Error("Provide a grounded question."), "Provide a grounded question.", {
        question: input,
        osis: osis || undefined,
      });
      return;
    }

    const nextMessages = [...messages, createUserMessage(question)];
    setMessages(nextMessages);
    setIsSending(true);
    clearError();
    setSearchPanelOpen(false);
    setUploadPanelOpen(false);

    try {
      const payload = await apiClient.runChatTurn({
        messages: nextMessages,
        session_id: sessionId ?? undefined,
        osis: osis.trim() || undefined,
        model: mode.id,
      });
      setSessionId(payload.session_id);
      const assistantMessage: ChatMessage = payload.message;
      setMessages([...nextMessages, assistantMessage]);
      setInput("");
    } catch (error) {
      recordError(error, "Unable to send the chat turn", {
        question,
        osis: osis || undefined,
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleResetSession = () => {
    setSessionId(null);
    setMessages([]);
    setInput("");
    setOsis("");
    clearError();
    setSearchPanelOpen(false);
    setUploadPanelOpen(false);
  };

  const handleLaunchSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const params = new URLSearchParams();
    if (searchPrefill.query) {
      params.set("q", searchPrefill.query);
    }
    if (searchPrefill.osis) {
      params.set("osis", searchPrefill.osis);
    }
    const queryString = params.toString();
    router.push(queryString ? `/search?${queryString}` : "/search");
  };

  return (
    <section>
      <h2>Chat</h2>
      <p>Ask grounded questions and receive answers anchored to your corpus.</p>
      <ModeChangeBanner area="Chat workspace" />

      <form
        onSubmit={handleSubmit}
        style={{ display: "grid", gap: "0.75rem", maxWidth: 640, marginBottom: "1.5rem" }}
      >
        <label style={{ display: "grid", gap: "0.35rem" }}>
          Your question
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            rows={4}
            required
            placeholder="What themes emerge in John 1:1?"
            style={{ padding: "0.75rem", borderRadius: "0.75rem", border: "1px solid #cbd5f5" }}
          />
        </label>

        <label style={{ display: "grid", gap: "0.35rem" }}>
          Optional OSIS reference
          <input
            type="text"
            value={osis}
            onChange={(event) => setOsis(event.target.value)}
            placeholder="John.1.1"
            style={{ padding: "0.5rem", borderRadius: "0.75rem", border: "1px solid #cbd5f5" }}
          />
        </label>

        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button type="submit" className="button" disabled={isSending}>
            {isSending ? "Sending." : "Send"}
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={handleResetSession}
            disabled={isSending}
          >
            Reset conversation
          </button>
        </div>
      </form>

      {errorCallout && <div style={{ marginBottom: "1.5rem" }}>{errorCallout}</div>}

      <section aria-live="polite" style={{ display: "grid", gap: "1rem" }}>
        {messages.length ? (
          <ul
            style={{
              listStyle: "none",
              margin: 0,
              padding: 0,
              display: "grid",
              gap: "1rem",
            }}
          >
            {messages.map((message, index) => (
              <li
                key={`${message.role}-${index}`}
                style={{
                  background: message.role === "assistant" ? "#f4f8ff" : "#fff",
                  border: "1px solid #dbeafe",
                  borderRadius: "0.75rem",
                  padding: "1rem",
                }}
              >
                <p style={{ margin: "0 0 0.35rem 0", fontWeight: 600 }}>
                  {message.role === "assistant" ? "Theo" : "You"}
                </p>
                <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{message.content}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p style={{ color: "#4b5563" }}>
            Start the conversation by asking a question about your corpus or a specific passage.
          </p>
        )}
      </section>

      {searchPanelOpen && (
        <aside
          aria-label="Search follow-up"
          style={{
            marginTop: "2rem",
            padding: "1rem",
            borderRadius: "0.75rem",
            border: "1px solid #bfdbfe",
            background: "#eff6ff",
            display: "grid",
            gap: "0.75rem",
          }}
        >
          <h3 style={{ margin: 0 }}>Explore related passages</h3>
          <p style={{ margin: 0 }}>
            Run a search to find grounded material before sending a new turn.
          </p>
          <form onSubmit={handleLaunchSearch} style={{ display: "grid", gap: "0.5rem", maxWidth: 360 }}>
            <label style={{ display: "grid", gap: "0.25rem" }}>
              Search query
              <input
                type="text"
                value={searchPrefill.query ?? ""}
                onChange={(event) =>
                  setSearchPrefill((prev) => ({ ...prev, query: event.target.value }))
                }
                style={{ padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid #93c5fd" }}
              />
            </label>
            <label style={{ display: "grid", gap: "0.25rem" }}>
              OSIS filter
              <input
                type="text"
                value={searchPrefill.osis ?? ""}
                onChange={(event) =>
                  setSearchPrefill((prev) => ({ ...prev, osis: event.target.value || null }))
                }
                style={{ padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid #93c5fd" }}
              />
            </label>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button type="submit" className="button">
                Open in search
              </button>
              <button
                type="button"
                className="button secondary"
                onClick={() => setSearchPanelOpen(false)}
              >
                Close
              </button>
            </div>
          </form>
        </aside>
      )}

      {uploadPanelOpen && (
        <aside
          aria-label="Upload follow-up"
          style={{
            marginTop: "2rem",
            padding: "1rem",
            borderRadius: "0.75rem",
            border: "1px solid #fcd34d",
            background: "#fffbeb",
            display: "grid",
            gap: "0.75rem",
          }}
        >
          <h3 style={{ margin: 0 }}>Add supporting documents</h3>
          <p style={{ margin: 0 }}>
            Upload transcripts or notes so the assistant can cite them in future responses.
          </p>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button type="button" className="button" onClick={() => router.push("/upload")}>
              Go to upload
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => setUploadPanelOpen(false)}
            >
              Close
            </button>
          </div>
        </aside>
      )}
    </section>
  );
}
