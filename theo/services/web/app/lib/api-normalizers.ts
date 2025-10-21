import type { components } from "./generated/api";
import type {
  GuardrailFailureMetadata,
  GuardrailSuggestion,
  HybridSearchFilters,
} from "./guardrails";
import {
  normaliseReasoningTrace,
  type ReasoningTrace,
} from "./reasoning-trace";

type ExportDeliverableResponse = components["schemas"]["ExportDeliverableResponse"];
type RAGAnswer = import("../copilot/components/types").RAGAnswer;
type RAGCitation = import("../copilot/components/types").RAGCitation;
type FallacyWarningModel = import("../copilot/components/types").FallacyWarningModel;
type ReasoningTraceType = ReasoningTrace;

export type ChatSessionPreferencesPayload = {
  mode?: string | null;
  defaultFilters?: HybridSearchFilters | null;
  frequentlyOpenedPanels?: string[];
};

export type ChatSessionMemoryEntry = {
  question: string;
  answer: string;
  answerSummary?: string | null;
  citations: RAGCitation[];
  documentIds: string[];
  createdAt: string;
  reasoningTrace?: ReasoningTraceType | null;
};

export type ResearchPlanStepStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "skipped"
  | "blocked";

export type ResearchPlanStep = {
  id: string;
  kind: string;
  index: number;
  label: string;
  query: string | null;
  tool: string | null;
  status: ResearchPlanStepStatus;
  estimatedTokens: number | null;
  estimatedCostUsd: number | null;
  estimatedDurationSeconds: number | null;
  actualTokens: number | null;
  actualCostUsd: number | null;
  actualDurationSeconds: number | null;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
};

export type ResearchPlan = {
  sessionId: string;
  steps: ResearchPlanStep[];
  activeStepId: string | null;
  version: number;
  updatedAt: string;
  metadata: Record<string, unknown>;
};

export type ChatSessionState = {
  sessionId: string;
  stance?: string | null;
  summary?: string | null;
  documentIds: string[];
  preferences?: {
    mode?: string | null;
    defaultFilters?: HybridSearchFilters | null;
    frequentlyOpenedPanels: string[];
  } | null;
  memory: ChatSessionMemoryEntry[];
  createdAt: string;
  updatedAt: string;
  lastInteractionAt: string;
  plan: ResearchPlan | null;
};

export type NormalisedChatCompletion = {
  sessionId: string;
  answer: RAGAnswer;
  plan: ResearchPlan | null;
};

export function normaliseExportResponse(
  payload: ExportDeliverableResponse,
): import("../copilot/components/types").ExportPresetResult {
  return {
    preset: payload.preset,
    format: payload.format,
    filename: payload.filename,
    mediaType: payload.media_type,
    content: payload.content,
  };
}

export function toOptionalString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function coerceStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((entry) => toOptionalString(entry))
    .filter((entry): entry is string => entry !== null);
}

const PLAN_STATUSES: ReadonlySet<ResearchPlanStepStatus> = new Set([
  "pending",
  "in_progress",
  "completed",
  "skipped",
  "blocked",
]);

function parseNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed) {
      const parsed = Number(trimmed);
      if (!Number.isNaN(parsed) && Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return null;
}

function parseMetadata(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return { ...(value as Record<string, unknown>) };
  }
  return {};
}

function normaliseResearchPlanStep(value: unknown): ResearchPlanStep | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const id = toOptionalString(record.id);
  const kind = toOptionalString(record.kind);
  const label = toOptionalString(record.label);
  const indexValue = parseNumber(record.index);
  if (!id || !kind || !label || indexValue === null) {
    return null;
  }
  const statusRaw = toOptionalString(record.status) ?? "pending";
  const status = PLAN_STATUSES.has(statusRaw as ResearchPlanStepStatus)
    ? (statusRaw as ResearchPlanStepStatus)
    : "pending";
  return {
    id,
    kind,
    index: Math.max(0, Math.trunc(indexValue)),
    label,
    query: toOptionalString(record.query),
    tool: toOptionalString(record.tool),
    status,
    estimatedTokens: parseNumber(record.estimated_tokens ?? record.estimatedTokens),
    estimatedCostUsd: parseNumber(record.estimated_cost_usd ?? record.estimatedCostUsd),
    estimatedDurationSeconds: parseNumber(
      record.estimated_duration_seconds ?? record.estimatedDurationSeconds,
    ),
    actualTokens: parseNumber(record.actual_tokens ?? record.actualTokens),
    actualCostUsd: parseNumber(record.actual_cost_usd ?? record.actualCostUsd),
    actualDurationSeconds: parseNumber(
      record.actual_duration_seconds ?? record.actualDurationSeconds,
    ),
    metadata: parseMetadata(record.metadata),
    createdAt:
      toOptionalString(record.created_at ?? record.createdAt) ?? new Date().toISOString(),
    updatedAt:
      toOptionalString(record.updated_at ?? record.updatedAt) ?? new Date().toISOString(),
  } satisfies ResearchPlanStep;
}

export function normaliseResearchPlan(value: unknown): ResearchPlan | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const sessionId = toOptionalString(record.session_id ?? record.sessionId);
  if (!sessionId) {
    return null;
  }
  const stepsSource = Array.isArray(record.steps) ? record.steps : [];
  const steps = stepsSource
    .map((entry) => normaliseResearchPlanStep(entry))
    .filter((entry): entry is ResearchPlanStep => entry !== null)
    .sort((a, b) => a.index - b.index);
  return {
    sessionId,
    steps,
    activeStepId: toOptionalString(record.active_step_id ?? record.activeStepId),
    version: parseNumber(record.version) ?? 1,
    updatedAt:
      toOptionalString(record.updated_at ?? record.updatedAt) ?? new Date().toISOString(),
    metadata: parseMetadata(record.metadata),
  } satisfies ResearchPlan;
}

const GUARDRAIL_ACTIONS = new Set(["search", "upload", "retry", "none"]);
const GUARDRAIL_KINDS = new Set(["retrieval", "generation", "safety", "ingest"]);

export function parseHybridFilters(value: unknown): HybridSearchFilters | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const filters: HybridSearchFilters = {};
  let hasValue = false;
  const assign = (key: keyof HybridSearchFilters, candidate: unknown) => {
    if (typeof candidate === "string") {
      const normalized = candidate.trim();
      if (normalized) {
        filters[key] = normalized;
        hasValue = true;
      }
    }
  };
  assign("collection", record.collection);
  assign("author", record.author);
  assign("source_type", record.source_type);
  assign("theological_tradition", record.theological_tradition);
  assign("topic_domain", record.topic_domain);
  return hasValue ? filters : null;
}

export function parseGuardrailSuggestion(value: unknown): GuardrailSuggestion | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const label = toOptionalString(record.label);
  if (!label) {
    return null;
  }
  const action = (toOptionalString(record.action) ?? "search").toLowerCase();
  const description = toOptionalString(record.description);
  if (action === "upload") {
    return {
      action: "upload",
      label,
      description,
      collection: toOptionalString(record.collection),
    } satisfies GuardrailSuggestion;
  }
  return {
    action: "search",
    label,
    description,
    query: toOptionalString(record.query),
    osis: toOptionalString(record.osis),
    filters: parseHybridFilters(record.filters ?? null),
  } satisfies GuardrailSuggestion;
}

export function parseGuardrailMetadata(value: unknown): GuardrailFailureMetadata | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const code = toOptionalString(record.code) ?? "guardrail_violation";
  const guardrailRaw = toOptionalString(record.guardrail)?.toLowerCase();
  const guardrail = guardrailRaw && GUARDRAIL_KINDS.has(guardrailRaw)
    ? (guardrailRaw as GuardrailFailureMetadata["guardrail"])
    : "unknown";
  const suggestedRaw =
    toOptionalString(record.suggested_action ?? record.suggestedAction)?.toLowerCase() ??
    (guardrail === "ingest" ? "upload" : "search");
  const suggestedAction = GUARDRAIL_ACTIONS.has(suggestedRaw)
    ? (suggestedRaw as GuardrailFailureMetadata["suggestedAction"])
    : (guardrail === "ingest" ? "upload" : "search");
  const safeRefusal =
    typeof record.safe_refusal === "boolean"
      ? record.safe_refusal
      : typeof record.safeRefusal === "boolean"
      ? record.safeRefusal
      : false;
  return {
    code,
    guardrail,
    suggestedAction,
    filters: parseHybridFilters(record.filters ?? null),
    safeRefusal,
    reason: toOptionalString(record.reason),
  } satisfies GuardrailFailureMetadata;
}

function buildGuardrailPayload(record: Record<string, unknown>) {
  const detailValue = record.detail;
  const detailRecord =
    detailValue && typeof detailValue === "object" ? (detailValue as Record<string, unknown>) : record;
  const detailString =
    typeof detailValue === "string" ? toOptionalString(detailValue) : undefined;
  const message =
    toOptionalString(detailRecord.message) ??
    detailString ??
    toOptionalString(record.message) ??
    "Response was blocked by content guardrails.";
  const traceId =
    toOptionalString(
      detailRecord.trace_id ??
        detailRecord.traceId ??
        detailRecord.trace ??
        record.trace_id ??
        record.traceId ??
        record.trace ??
        record.id ??
        record.reference,
    ) ?? null;
  const suggestionsSource =
    Array.isArray(detailRecord.suggestions) ? detailRecord.suggestions : [];
  const suggestions = suggestionsSource
    .map((entry) => parseGuardrailSuggestion(entry))
    .filter((entry): entry is GuardrailSuggestion => entry !== null);
  const metadataValue =
    detailRecord.metadata ??
    detailRecord.guardrail_metadata ??
    record.metadata ??
    null;
  const metadata = parseGuardrailMetadata(metadataValue);
  return { message, traceId, suggestions, metadata } satisfies {
    message: string;
    traceId: string | null;
    suggestions: GuardrailSuggestion[];
    metadata: GuardrailFailureMetadata | null;
  };
}

export function parseGuardrailPayload(
  payload: unknown,
): {
  message: string;
  traceId: string | null;
  suggestions: GuardrailSuggestion[];
  metadata: GuardrailFailureMetadata | null;
} | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const typeValue = toOptionalString(record.type) ?? toOptionalString(record.reason);
  if (typeValue && typeValue.toLowerCase().includes("guardrail")) {
    return buildGuardrailPayload(record);
  }

  if (typeof record.guardrail === "object" && record.guardrail) {
    const nested = parseGuardrailPayload(record.guardrail);
    if (nested) {
      return nested;
    }
  }

  if (Array.isArray(record.detail)) {
    for (const item of record.detail) {
      const nested = parseGuardrailPayload(item);
      if (nested) {
        return nested;
      }
    }
  } else if (record.detail && typeof record.detail === "object") {
    const nested = parseGuardrailPayload(record.detail);
    if (nested) {
      return nested;
    }
  }

  return null;
}

export function normaliseCitation(value: unknown): RAGCitation | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const index = typeof record.index === "number" ? record.index : null;
  const osis = toOptionalString(record.osis);
  const anchor = toOptionalString(record.anchor);
  const passageId = toOptionalString(record.passage_id);
  const documentId = toOptionalString(record.document_id);
  const snippet = toOptionalString(record.snippet);
  if (
    index == null ||
    !osis ||
    !anchor ||
    !passageId ||
    !documentId ||
    !snippet
  ) {
    return null;
  }
  return {
    index,
    osis,
    anchor,
    passage_id: passageId,
    document_id: documentId,
    snippet,
    document_title: toOptionalString(record.document_title),
    source_url: toOptionalString(record.source_url),
  };
}

export function normaliseFallacyWarning(value: unknown): FallacyWarningModel | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const fallacyType = toOptionalString(record.fallacy_type ?? record.fallacyType);
  const description = toOptionalString(record.description);
  const matchedText = toOptionalString(record.matched_text ?? record.matchedText);
  if (!fallacyType || !description) {
    return null;
  }
  const severityRaw = toOptionalString(record.severity)?.toLowerCase();
  const severity = severityRaw === "high" || severityRaw === "low" || severityRaw === "medium"
    ? severityRaw
    : "medium";
  const suggestion = toOptionalString(record.suggestion);
  return {
    fallacy_type: fallacyType,
    severity,
    description,
    matched_text: matchedText ?? "",
    suggestion,
  } satisfies FallacyWarningModel;
}

export function normaliseAnswer(value: unknown): RAGAnswer | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const summary = toOptionalString(record.summary) ?? "";
  const citations = Array.isArray(record.citations)
    ? record.citations.map(normaliseCitation).filter((citation): citation is RAGCitation => citation !== null)
    : [];
  const modelName = toOptionalString(record.model_name);
  const modelOutput = toOptionalString(record.model_output);
  const guardrailProfile =
    record.guardrail_profile && typeof record.guardrail_profile === "object"
      ? (record.guardrail_profile as Record<string, string>)
      : null;
  const fallacySources = Array.isArray(record.fallacy_warnings)
    ? record.fallacy_warnings
    : Array.isArray(record.fallacies_found)
    ? record.fallacies_found
    : [];
  const fallacyWarnings = fallacySources
    .map((entry) => normaliseFallacyWarning(entry))
    .filter((entry): entry is FallacyWarningModel => entry !== null);
  const reasoningTrace = normaliseReasoningTrace(
    record.reasoning_trace ?? record.reasoningTrace ?? null,
  );

  return {
    summary,
    citations,
    model_name: modelName ?? null,
    model_output: modelOutput ?? null,
    guardrail_profile: guardrailProfile,
    fallacy_warnings: fallacyWarnings,
    reasoning_trace: reasoningTrace as ReasoningTraceType | null,
  };
}

export function normaliseChatCompletion(
  payload: unknown,
  fallbackSessionId: string | null,
): NormalisedChatCompletion | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const answer = normaliseAnswer(record.answer ?? record.result ?? null);
  if (!answer) {
    return null;
  }
  const sessionId =
    toOptionalString(record.session_id ?? record.sessionId ?? record.id) ?? fallbackSessionId ?? "session";
  const plan = normaliseResearchPlan(record.plan ?? null);
  return { sessionId, answer, plan };
}

export function normaliseChatSessionState(payload: unknown): ChatSessionState | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const sessionId = toOptionalString(record.session_id ?? record.sessionId ?? record.id);
  if (!sessionId) {
    return null;
  }
  const stance = toOptionalString(record.stance);
  const summary = toOptionalString(record.summary);
  const createdAt = toOptionalString(record.created_at ?? record.createdAt);
  const updatedAt = toOptionalString(record.updated_at ?? record.updatedAt);
  const lastInteractionAt = toOptionalString(record.last_interaction_at ?? record.lastInteractionAt);

  const documentIds = coerceStringList(record.document_ids ?? record.documentIds);

  const memoryItems = Array.isArray(record.memory) ? record.memory : [];
  const memory: ChatSessionMemoryEntry[] = [];
  for (const item of memoryItems) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const data = item as Record<string, unknown>;
    const question = toOptionalString(data.question);
    const answer = toOptionalString(data.answer);
    if (!question || !answer) {
      continue;
    }
    const answerSummary = toOptionalString(data.answer_summary ?? data.answerSummary ?? null);
    const created = toOptionalString(data.created_at ?? data.createdAt) ?? new Date().toISOString();
    const citationsRaw = Array.isArray(data.citations) ? data.citations : [];
    const citations: RAGCitation[] = citationsRaw
      .map((citation) => normaliseCitation(citation))
      .filter((value): value is RAGCitation => value != null);
    const reasoningTrace = normaliseReasoningTrace(
      data.reasoning_trace ?? data.reasoningTrace ?? null,
    );
    const documentIdsEntry = coerceStringList(data.document_ids ?? data.documentIds);
    memory.push({
      question,
      answer,
      answerSummary,
      citations,
      documentIds: documentIdsEntry,
      createdAt: created,
      reasoningTrace,
    });
  }

  let preferences: ChatSessionState["preferences"] = null;
  if (record.preferences && typeof record.preferences === "object") {
    const pref = record.preferences as Record<string, unknown>;
    const mode = toOptionalString(pref.mode);
    const defaultFilters = parseHybridFilters(pref.default_filters ?? pref.defaultFilters);
    const frequentlyOpenedPanels = coerceStringList(
      pref.frequently_opened_panels ?? pref.frequentlyOpenedPanels,
    );
    preferences = {
      mode,
      defaultFilters,
      frequentlyOpenedPanels,
    };
  }

  const plan = normaliseResearchPlan(record.plan ?? null);

  const fallbackTimestamp = new Date().toISOString();

  return {
    sessionId,
    stance,
    summary,
    documentIds,
    preferences,
    memory,
    createdAt: createdAt ?? fallbackTimestamp,
    updatedAt: updatedAt ?? createdAt ?? fallbackTimestamp,
    lastInteractionAt: lastInteractionAt ?? updatedAt ?? createdAt ?? fallbackTimestamp,
    plan,
  };
}
