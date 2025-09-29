import { ApiError, isApiError } from "./api-error";

export type FailureContext = {
  question?: string | null;
  osis?: string | null;
};

export type SuggestionAction =
  | {
      kind: "open-search";
      label?: string;
      query?: string;
      osis?: string | null;
    }
  | { kind: "open-upload"; label?: string }
  | { kind: "focus-input"; label?: string };

export type FailureSuggestion = {
  title: string;
  description: string;
  action: SuggestionAction;
};

export type SuggestionHandlers = {
  openSearchPanel?: (params: { query?: string; osis?: string | null }) => void;
  openUploadPanel?: () => void;
  focusInput?: () => void;
};

const SEARCH_CODES = new Set<string>([
  "guardrail_profile_no_match",
  "retrieval_missing_osis",
  "completion_empty",
  "completion_missing_sources_section",
  "completion_missing_citations",
  "completion_unrecognized_citations",
  "completion_citation_mismatch",
  "completion_safety_violation",
]);

const UPLOAD_CODES = new Set<string>(["guardrail_document_missing"]);

const INPUT_CODES = new Set<string>([
  "chat_blank_user_message",
  "chat_missing_user_message",
  "chat_empty_messages",
]);

function normaliseQuery(context: FailureContext): { query?: string; osis?: string | null } {
  const query = context.question?.trim();
  const osis = context.osis?.trim() || null;
  return { query: query || undefined, osis };
}

export function buildFailureSuggestion(
  code: string | undefined,
  context: FailureContext,
): FailureSuggestion | null {
  if (!code) {
    return null;
  }

  if (INPUT_CODES.has(code)) {
    return {
      title: "Update your request",
      description: "Add a grounded question or passage before sending the turn.",
      action: { kind: "focus-input", label: "Edit prompt" },
    } satisfies FailureSuggestion;
  }

  if (UPLOAD_CODES.has(code)) {
    return {
      title: "Add supporting sources",
      description:
        "Upload documents or transcripts so the assistant has grounded material to cite.",
      action: { kind: "open-upload", label: "Open upload panel" },
    } satisfies FailureSuggestion;
  }

  if (SEARCH_CODES.has(code) || code.startsWith("completion_")) {
    const params = normaliseQuery(context);
    return {
      title: "No grounded sources were available",
      description:
        "Try searching the library or broadening filters to locate passages you can cite.",
      action: {
        kind: "open-search",
        label: "Open search panel",
        query: params.query,
        osis: params.osis,
      },
    } satisfies FailureSuggestion;
  }

  if (code === "chat_payload_too_large") {
    return {
      title: "Prompt too long",
      description: "Trim the conversation or send a shorter question before retrying.",
      action: { kind: "focus-input", label: "Edit prompt" },
    } satisfies FailureSuggestion;
  }

  return null;
}

export function suggestionFromError(
  error: unknown,
  context: FailureContext,
): FailureSuggestion | null {
  if (!isApiError(error)) {
    return null;
  }
  return buildFailureSuggestion(error.code, context);
}

export function dispatchSuggestionAction(
  action: SuggestionAction,
  handlers: SuggestionHandlers,
): void {
  switch (action.kind) {
    case "open-search":
      handlers.openSearchPanel?.({ query: action.query, osis: action.osis ?? null });
      break;
    case "open-upload":
      handlers.openUploadPanel?.();
      break;
    case "focus-input":
      handlers.focusInput?.();
      break;
    default: {
      const neverAction: never = action;
      throw new Error(`Unhandled suggestion action: ${JSON.stringify(neverAction)}`);
    }
  }
}

export function extractTraceId(error: unknown): string | null {
  if (isApiError(error)) {
    return error.traceId ?? null;
  }
  if (error && typeof error === "object" && "traceId" in error) {
    const candidate = (error as { traceId?: string | null }).traceId;
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return null;
}
