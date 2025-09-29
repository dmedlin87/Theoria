"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  createTheoApiClient,
  type ChatSessionMessage,
} from "../lib/api-client";
import { useMode } from "../mode-context";

const STORAGE_KEY = "theo.chat.workspace";

type FilterState = {
  collection: string;
  theological_tradition: string;
  topic_domain: string;
};

type StoredWorkspaceState = {
  sessionId: string | null;
  messages: ChatSessionMessage[];
  filters: FilterState;
  panels: string[];
};

const EMPTY_FILTERS: FilterState = {
  collection: "",
  theological_tradition: "",
  topic_domain: "",
};

function normaliseFilters(filters: FilterState): Partial<FilterState> {
  return {
    collection: filters.collection.trim(),
    theological_tradition: filters.theological_tradition.trim(),
    topic_domain: filters.topic_domain.trim(),
  };
}

function parsePanels(value: string): string[] {
  return value
    .split(",")
    .map((panel) => panel.trim())
    .filter((panel) => panel.length > 0);
}

export default function ChatWorkspacePage(): JSX.Element {
  const { mode } = useMode();
  const apiClient = useMemo(() => createTheoApiClient(), []);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatSessionMessage[]>([]);
  const [input, setInput] = useState("");
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [panelsInput, setPanelsInput] = useState("");
  const [sessionSummary, setSessionSummary] = useState<string | null>(null);
  const [sessionStance, setSessionStance] = useState<string | null>(null);
  const [memorySnippets, setMemorySnippets] = useState<string[]>([]);
  const [linkedDocuments, setLinkedDocuments] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingSession, setIsLoadingSession] = useState(false);

  const loadSessionDetails = useCallback(
    async (id: string) => {
      setIsLoadingSession(true);
      try {
        const detail = await apiClient.fetchChatSession(id);
        setSessionSummary(detail.summary ?? null);
        setSessionStance(detail.stance ?? null);
        setMemorySnippets(detail.memory_snippets ?? []);
        setLinkedDocuments(detail.linked_document_ids ?? []);
        if (detail.preferences?.default_filters) {
          setFilters((prev) => ({
            collection:
              detail.preferences?.default_filters?.collection ?? prev.collection ?? "",
            theological_tradition:
              detail.preferences?.default_filters?.theological_tradition ??
              prev.theological_tradition ??
              "",
            topic_domain:
              detail.preferences?.default_filters?.topic_domain ?? prev.topic_domain ?? "",
          }));
        }
        if (detail.preferences?.frequently_opened_panels) {
          setPanelsInput(detail.preferences.frequently_opened_panels.join(", "));
        }
      } catch (fetchError) {
        setError((fetchError as Error).message || "Unable to load chat session");
      } finally {
        setIsLoadingSession(false);
      }
    },
    [apiClient],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const storedRaw = window.localStorage.getItem(STORAGE_KEY);
    if (!storedRaw) {
      return;
    }
    try {
      const stored = JSON.parse(storedRaw) as StoredWorkspaceState;
      if (stored.messages) {
        setMessages(stored.messages);
      }
      if (stored.filters) {
        setFilters({
          collection: stored.filters.collection ?? "",
          theological_tradition: stored.filters.theological_tradition ?? "",
          topic_domain: stored.filters.topic_domain ?? "",
        });
      }
      if (stored.panels) {
        setPanelsInput(stored.panels.join(", "));
      }
      if (stored.sessionId) {
        setSessionId(stored.sessionId);
        void loadSessionDetails(stored.sessionId);
      }
    } catch (parseError) {
      console.warn("Unable to parse stored chat workspace state", parseError);
    }
  }, [loadSessionDetails]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const payload: StoredWorkspaceState = {
      sessionId,
      messages,
      filters,
      panels: parsePanels(panelsInput),
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [sessionId, messages, filters, panelsInput]);

  const handleFilterChange = (field: keyof FilterState) =>
    (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value;
      setFilters((prev) => ({ ...prev, [field]: value }));
    };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) {
      return;
    }
    setError(null);
    const userMessage: ChatSessionMessage = { role: "user", content: trimmed };
    const previousMessages = messages;
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setIsSending(true);

    try {
      const normalizedFilters = normaliseFilters(filters);
      const requestFilters: Record<string, string> = {};
      if (normalizedFilters.collection) {
        requestFilters.collection = normalizedFilters.collection;
      }
      if (normalizedFilters.theological_tradition) {
        requestFilters.theological_tradition = normalizedFilters.theological_tradition;
      }
      if (normalizedFilters.topic_domain) {
        requestFilters.topic_domain = normalizedFilters.topic_domain;
      }
      const frequentPanels = parsePanels(panelsInput);
      const response = await apiClient.runChatTurn({
        sessionId: sessionId ?? undefined,
        messages: nextMessages,
        model: mode.id,
        filters: Object.keys(requestFilters).length ? requestFilters : null,
        preferences: {
          mode: mode.id,
          default_filters: Object.keys(requestFilters).length ? requestFilters : null,
          frequently_opened_panels: frequentPanels.length ? frequentPanels : null,
        },
      });
      setSessionId(response.session_id);
      setMessages([...nextMessages, response.message]);
      setInput("");
      setSessionSummary(response.answer.summary ?? null);
      const linked = Array.from(
        new Set(
          response.answer.citations
            ?.map((citation) => citation.document_id)
            .filter((value): value is string => Boolean(value)) ?? [],
        ),
      );
      setLinkedDocuments(linked);
      await loadSessionDetails(response.session_id);
    } catch (sendError) {
      setMessages(previousMessages);
      setError((sendError as Error).message || "Unable to send message");
    } finally {
      setIsSending(false);
    }
  };

  const handleReset = () => {
    setSessionId(null);
    setMessages([]);
    setInput("");
    setSessionSummary(null);
    setSessionStance(null);
    setMemorySnippets([]);
    setLinkedDocuments([]);
    setError(null);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  };

  const handleFork = () => {
    if (!messages.length) {
      return;
    }
    setSessionId(null);
    setSessionSummary(null);
    setSessionStance(null);
    setMemorySnippets([]);
    setLinkedDocuments([]);
    setError(null);
  };

  return (
    <section style={{ display: "grid", gap: "1.5rem" }}>
      <header style={{ display: "grid", gap: "0.5rem" }}>
        <h2>Chat workspace</h2>
        <p style={{ margin: 0 }}>
          Active session: <strong>{sessionId ?? "New session"}</strong>
        </p>
        {sessionSummary && (
          <p style={{ margin: 0 }}>
            <strong>Latest summary:</strong> {sessionSummary}
          </p>
        )}
        {sessionStance && (
          <p style={{ margin: 0 }}>
            <strong>Stance:</strong> {sessionStance}
          </p>
        )}
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button type="button" onClick={handleReset} className="button secondary">
            Reset session
          </button>
          <button
            type="button"
            onClick={handleFork}
            className="button secondary"
            disabled={!messages.length}
          >
            Fork session
          </button>
        </div>
        {error && (
          <p role="alert" style={{ color: "var(--error)", margin: 0 }}>
            {error}
          </p>
        )}
      </header>

      <section style={{ display: "grid", gap: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Preferences</h3>
        <div style={{ display: "grid", gap: "0.75rem", maxWidth: 480 }}>
          <label>
            Collection filter
            <input
              type="text"
              value={filters.collection}
              onChange={handleFilterChange("collection")}
              placeholder="e.g. Gospels"
            />
          </label>
          <label>
            Theological tradition
            <input
              type="text"
              value={filters.theological_tradition}
              onChange={handleFilterChange("theological_tradition")}
              placeholder="e.g. anglican"
            />
          </label>
          <label>
            Topic domain
            <input
              type="text"
              value={filters.topic_domain}
              onChange={handleFilterChange("topic_domain")}
              placeholder="e.g. christology"
            />
          </label>
          <label>
            Frequently opened panels (comma separated)
            <input
              type="text"
              value={panelsInput}
              onChange={(event) => setPanelsInput(event.target.value)}
              placeholder="citations, outline"
            />
          </label>
        </div>
      </section>

      <section style={{ display: "grid", gap: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Memory</h3>
        {isLoadingSession && <p>Loading session memory…</p>}
        {!isLoadingSession && memorySnippets.length === 0 && <p>No memory captured yet.</p>}
        {!isLoadingSession && memorySnippets.length > 0 && (
          <ul style={{ paddingLeft: "1.25rem", margin: 0, display: "grid", gap: "0.5rem" }}>
            {memorySnippets.map((snippet, index) => (
              <li key={index}>{snippet}</li>
            ))}
          </ul>
        )}
        {linkedDocuments.length > 0 && (
          <p style={{ margin: 0 }}>
            <strong>Linked documents:</strong> {linkedDocuments.join(", ")}
          </p>
        )}
      </section>

      <section style={{ display: "grid", gap: "1rem" }}>
        <h3 style={{ margin: 0 }}>Conversation</h3>
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: "0.5rem",
            padding: "1rem",
            minHeight: "240px",
            display: "grid",
            gap: "0.75rem",
            background: "var(--surface)",
          }}
        >
          {messages.length === 0 && <p style={{ margin: 0 }}>Start the conversation by asking a question.</p>}
          {messages.map((message, index) => (
            <article key={index} style={{ display: "grid", gap: "0.25rem" }}>
              <h4 style={{ margin: 0, fontSize: "0.95rem" }}>{
                message.role === "user" ? "You" : message.role === "assistant" ? "Theo" : "System"
              }</h4>
              <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{message.content}</p>
            </article>
          ))}
        </div>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: "0.75rem" }}>
          <label htmlFor="chat-input" style={{ fontWeight: 600 }}>
            Ask a grounded question
          </label>
          <textarea
            id="chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            rows={4}
            placeholder="How does John 1:1 describe the Logos?"
            style={{ width: "100%", fontSize: "1rem" }}
            disabled={isSending}
          />
          <button type="submit" className="button" disabled={isSending}>
            {isSending ? "Sending…" : "Send"}
          </button>
        </form>
      </section>
    </section>
  );
}
