"use client";

import { parseErrorResponse } from "./errorUtils";

type TelemetryEventInput = {
  event: string;
  durationMs: number;
  workflow?: string;
  metadata?: Record<string, unknown>;
};

type TelemetryPayload = {
  events: Array<{
    event: string;
    duration_ms: number;
    workflow?: string;
    metadata?: Record<string, unknown>;
  }>;
  page?: string | null;
};

export async function emitTelemetry(
  events: TelemetryEventInput[],
  context?: { page?: string },
): Promise<void> {
  if (events.length === 0) {
    return;
  }
  const payload: TelemetryPayload = {
    events: events.map((event) => ({
      event: event.event,
      duration_ms: Math.max(0, event.durationMs),
      ...(event.workflow ? { workflow: event.workflow } : {}),
      ...(event.metadata ? { metadata: event.metadata } : {}),
    })),
  };
  if (context && "page" in context) {
    payload.page = context.page ?? null;
  }
  try {
    const response = await fetch("/api/analytics/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok && process.env.NODE_ENV !== "production") {
      const details = await parseErrorResponse(
        response,
        `Telemetry submission failed with status ${response.status}`,
      );
      console.debug(
        `Telemetry endpoint responded with ${response.status}: ${details.message}`,
        details.traceId ? { traceId: details.traceId } : undefined,
      );
    }
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.debug("Failed to emit telemetry", error);
    }
  }
}

export type FeedbackAction =
  | "view"
  | "click"
  | "copy"
  | "like"
  | "dislike"
  | "used_in_answer"
  | (string & {});

export type FeedbackEventInput = {
  action: FeedbackAction;
  userId?: string | null;
  chatSessionId?: string | null;
  query?: string | null;
  documentId?: string | null;
  passageId?: string | null;
  rank?: number | null;
  score?: number | null;
  confidence?: number | null;
};

export async function submitFeedback(payload: FeedbackEventInput): Promise<void> {
  const body: Record<string, unknown> = { action: payload.action };
  if (payload.userId) body.user_id = payload.userId;
  if (payload.chatSessionId) body.chat_session_id = payload.chatSessionId;
  if (payload.query) body.query = payload.query;
  if (payload.documentId) body.document_id = payload.documentId;
  if (payload.passageId) body.passage_id = payload.passageId;
  if (typeof payload.rank === "number") body.rank = payload.rank;
  if (typeof payload.score === "number") body.score = payload.score;
  if (typeof payload.confidence === "number") body.confidence = payload.confidence;

  try {
    const response = await fetch("/api/analytics/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok && process.env.NODE_ENV !== "production") {
      const details = await parseErrorResponse(
        response,
        `Feedback submission failed with status ${response.status}`,
      );
      console.debug(
        `Feedback endpoint responded with ${response.status}: ${details.message}`,
        details.traceId ? { traceId: details.traceId } : undefined,
      );
    }
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.debug("Failed to submit feedback", error);
    }
  }
}
