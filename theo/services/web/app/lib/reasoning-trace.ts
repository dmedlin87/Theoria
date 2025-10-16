export type ReasoningTraceStatus =
  | "pending"
  | "in_progress"
  | "supported"
  | "contradicted"
  | "uncertain"
  | "complete";

export type ReasoningTraceEvidence = {
  id: string;
  text: string;
  label?: string | null;
  citationIds?: number[] | null;
};

export type ReasoningTraceStep = {
  id: string;
  label: string;
  detail?: string | null;
  outcome?: string | null;
  status?: ReasoningTraceStatus | null;
  confidence?: number | null;
  citations?: number[] | null;
  evidence?: ReasoningTraceEvidence[] | null;
  children?: ReasoningTraceStep[] | null;
};

export type ReasoningTrace = {
  summary?: string | null;
  strategy?: string | null;
  steps: ReasoningTraceStep[];
};

export function normaliseReasoningTrace(value: unknown): ReasoningTrace | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const stepsSource = Array.isArray(record.steps) ? record.steps : [];
  const steps = stepsSource
    .map((entry, index) => normaliseReasoningStep(entry, index))
    .filter((step): step is ReasoningTraceStep => step !== null);

  if (steps.length === 0) {
    return null;
  }

  return {
    steps,
    summary: toOptionalString(record.summary),
    strategy: toOptionalString(record.strategy),
  } satisfies ReasoningTrace;
}

function normaliseReasoningStep(
  value: unknown,
  fallbackIndex: number
): ReasoningTraceStep | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const id = toOptionalString(record.id) ?? `step-${fallbackIndex}`;
  const label = toOptionalString(record.label) ?? "Reasoning step";
  const detail = toOptionalString(record.detail);
  const outcome = toOptionalString(record.outcome);
  const status = normaliseStatus(record.status);
  const confidence = typeof record.confidence === "number" ? record.confidence : null;
  const citations = Array.isArray(record.citations)
    ? record.citations
        .map((item) => (typeof item === "number" && Number.isFinite(item) ? Math.trunc(item) : null))
        .filter((item): item is number => item !== null)
    : [];
  const evidenceSource = Array.isArray(record.evidence) ? record.evidence : [];
  const evidence = evidenceSource
    .map((item, index) => normaliseEvidence(item, `${id}-evidence-${index}`))
    .filter((item): item is ReasoningTraceEvidence => item !== null);
  const childrenSource = Array.isArray(record.children) ? record.children : [];
  const children = childrenSource
    .map((child, index) => normaliseReasoningStep(child, index))
    .filter((child): child is ReasoningTraceStep => child !== null);

  return {
    id,
    label,
    detail,
    outcome,
    status,
    confidence,
    citations,
    evidence,
    children,
  } satisfies ReasoningTraceStep;
}

function normaliseEvidence(
  value: unknown,
  fallbackId: string
): ReasoningTraceEvidence | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const record = value as Record<string, unknown>;
  const text = toOptionalString(record.text);
  if (!text) {
    return null;
  }
  const citationIds = Array.isArray(record.citation_ids ?? record.citationIds)
    ? (record.citation_ids ?? record.citationIds ?? [])
        .map((item: unknown) =>
          typeof item === "number" && Number.isFinite(item) ? Math.trunc(item) : null
        )
        .filter((item): item is number => item !== null)
    : [];

  return {
    id: toOptionalString(record.id) ?? fallbackId,
    text,
    label: toOptionalString(record.label),
    citationIds,
  } satisfies ReasoningTraceEvidence;
}

function toOptionalString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function normaliseStatus(value: unknown): ReasoningTraceStatus | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalised = value.trim().toLowerCase();
  switch (normalised) {
    case "pending":
    case "in_progress":
    case "supported":
    case "contradicted":
    case "uncertain":
    case "complete":
      return normalised;
    default:
      return null;
  }
}

