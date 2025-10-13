"use client";

import Link from "next/link";
import { ThumbsDown, ThumbsUp } from "lucide-react";

import { Icon } from "../../../components/Icon";
import type { Reaction, AssistantConversationEntry } from "../../useChatWorkspaceState";

export type TranscriptEntry =
  | (AssistantConversationEntry & { displayContent: string; isActive: boolean })
  | ({ id: string; role: "user"; content: string } & {
      displayContent: string;
      isActive: boolean;
    });

type ChatTranscriptProps = {
  entries: TranscriptEntry[];
  hasTranscript: boolean;
  feedbackSelections: Partial<Record<string, Reaction>>;
  pendingFeedbackIds: Set<string>;
  onFeedback: (entryId: string, reaction: Reaction) => void | Promise<void>;
  sampleQuestions: string[];
  onSampleQuestionClick: (prompt: string, index: number) => void;
};

export function ChatTranscript({
  entries,
  hasTranscript,
  feedbackSelections,
  pendingFeedbackIds,
  onFeedback,
  sampleQuestions,
  onSampleQuestionClick,
}: ChatTranscriptProps): JSX.Element {
  if (!hasTranscript) {
    return (
      <div className="chat-empty-state">
        <h3>Start the conversation</h3>
        <p>Ask about a passage, doctrine, or theme and we’ll respond with cited insights.</p>
        <ul className="chat-empty-state-actions">
          {sampleQuestions.map((question, index) => (
            <li key={question}>
              <button
                type="button"
                className="chat-empty-state-chip"
                onClick={() => onSampleQuestionClick(question, index)}
              >
                {question}
              </button>
            </li>
          ))}
        </ul>
        <p className="chat-empty-state-links">
          Prefer browsing? Explore the <Link href="/search">Search</Link> and {" "}
          <Link href="/verse">Verse explorer</Link>.
        </p>
      </div>
    );
  }

  return (
    <>
      {entries.map((entry) => {
        const selection = feedbackSelections[entry.id] ?? null;
        const feedbackPending = pendingFeedbackIds.has(entry.id);
        const feedbackDisabled = feedbackPending || entry.isActive;
        const isAssistant = entry.role === "assistant";
        return (
          <article key={entry.id} className={`chat-message chat-message--${entry.role}`}>
            <header>{entry.role === "user" ? "You" : "Theo"}</header>
            <p aria-live={entry.isActive ? "polite" : undefined}>
              {entry.displayContent || "Awaiting response."}
            </p>
            {isAssistant && entry.citations.length > 0 && (
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
            {isAssistant && (
              <div className="chat-feedback-controls">
                <button
                  type="button"
                  className={`chat-feedback-button chat-feedback-button--positive${
                    selection === "like" ? " chat-feedback-button--active" : ""
                  }`}
                  onClick={() => onFeedback(entry.id, "like")}
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
                  onClick={() => onFeedback(entry.id, "dislike")}
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
      })}
    </>
  );
}
