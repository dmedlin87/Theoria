import { getApiBaseUrl } from "../../lib/api";

export type HypothesisStatus = "active" | "confirmed" | "refuted" | "uncertain";

export type HypothesisRecord = {
  id: string;
  claim: string;
  confidence: number;
  status: HypothesisStatus;
  trailId: string | null;
  supportingPassageIds: string[];
  contradictingPassageIds: string[];
  perspectiveScores: Record<string, number> | null;
  metadata: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
};

export type HypothesisFilters = {
  statuses: HypothesisStatus[];
  minConfidence?: number;
  query?: string;
};

export type HypothesisUpdateChanges = {
  claim?: string;
  confidence?: number;
  status?: HypothesisStatus;
  trailId?: string | null;
  supportingPassageIds?: string[] | null;
  contradictingPassageIds?: string[] | null;
  perspectiveScores?: Record<string, number> | null;
  metadata?: Record<string, unknown> | null;
};

type HypothesisApiRecord = {
  id: string;
  claim: string;
  confidence: number;
  status: HypothesisStatus;
  trail_id: string | null;
  supporting_passage_ids: string[] | null;
  contradicting_passage_ids: string[] | null;
  perspective_scores: Record<string, number> | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

type HypothesisListApiResponse = {
  hypotheses: HypothesisApiRecord[];
  total: number;
};

type HypothesisApiResponse = {
  hypothesis: HypothesisApiRecord;
};

function normalizeHypothesis(record: HypothesisApiRecord): HypothesisRecord {
  return {
    id: record.id,
    claim: record.claim,
    confidence: record.confidence,
    status: record.status,
    trailId: record.trail_id,
    supportingPassageIds: record.supporting_passage_ids ?? [],
    contradictingPassageIds: record.contradicting_passage_ids ?? [],
    perspectiveScores: record.perspective_scores,
    metadata: record.metadata,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
  };
}

function buildQueryString(filters: HypothesisFilters): string {
  const params = new URLSearchParams();
  filters.statuses.forEach((status) => params.append("status", status));
  if (typeof filters.minConfidence === "number") {
    params.set("min_confidence", filters.minConfidence.toString());
  }
  if (filters.query && filters.query.trim()) {
    params.set("q", filters.query.trim());
  }
  const queryString = params.toString();
  return queryString ? `?${queryString}` : "";
}

function buildUpdatePayload(changes: HypothesisUpdateChanges): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  if (typeof changes.claim === "string") {
    payload.claim = changes.claim;
  }
  if (typeof changes.confidence === "number") {
    payload.confidence = changes.confidence;
  }
  if (changes.status) {
    payload.status = changes.status;
  }
  if (Object.prototype.hasOwnProperty.call(changes, "trailId")) {
    payload.trail_id = changes.trailId ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(changes, "supportingPassageIds")) {
    payload.supporting_passage_ids = changes.supportingPassageIds ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(changes, "contradictingPassageIds")) {
    payload.contradicting_passage_ids = changes.contradictingPassageIds ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(changes, "perspectiveScores")) {
    payload.perspective_scores = changes.perspectiveScores ?? null;
  }
  if (Object.prototype.hasOwnProperty.call(changes, "metadata")) {
    payload.metadata = changes.metadata ?? null;
  }
  return payload;
}

function buildError(message: string, response: Response | null, error: unknown): Error {
  if (response) {
    return new Error(`${message} (status ${response.status})`);
  }
  if (error instanceof Error) {
    return new Error(`${message}: ${error.message}`);
  }
  return new Error(message);
}

export async function fetchHypotheses(
  filters: HypothesisFilters,
): Promise<{ hypotheses: HypothesisRecord[]; total: number }>
export async function fetchHypotheses(
  filters: HypothesisFilters,
  init?: RequestInit,
): Promise<{ hypotheses: HypothesisRecord[]; total: number }>
export async function fetchHypotheses(
  filters: HypothesisFilters,
  init?: RequestInit,
): Promise<{ hypotheses: HypothesisRecord[]; total: number }> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = `${baseUrl}/research/hypotheses${buildQueryString(filters)}`;
  let response: Response | null = null;
  try {
    response = await fetch(target, {
      cache: "no-store",
      ...init,
    });
    if (!response.ok) {
      throw buildError("Failed to load hypotheses", response, null);
    }
    const payload = (await response.json()) as HypothesisListApiResponse;
    return {
      hypotheses: payload.hypotheses.map(normalizeHypothesis),
      total: payload.total,
    };
  } catch (error) {
    if (response && response.ok) {
      throw error;
    }
    throw buildError("Failed to load hypotheses", response, error);
  }
}

export async function createHypothesis(
  payload: HypothesisUpdateChanges & { claim: string; confidence: number; status?: HypothesisStatus },
): Promise<HypothesisRecord> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/research/hypotheses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      claim: payload.claim,
      confidence: payload.confidence,
      status: payload.status ?? "active",
      trail_id: payload.trailId ?? null,
      supporting_passage_ids: payload.supportingPassageIds ?? null,
      contradicting_passage_ids: payload.contradictingPassageIds ?? null,
      perspective_scores: payload.perspectiveScores ?? null,
      metadata: payload.metadata ?? null,
    }),
  });
  if (!response.ok) {
    throw buildError("Failed to create hypothesis", response, null);
  }
  const payloadBody = (await response.json()) as HypothesisApiResponse;
  return normalizeHypothesis(payloadBody.hypothesis);
}

export async function updateHypothesis(
  hypothesisId: string,
  changes: HypothesisUpdateChanges,
): Promise<HypothesisRecord> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/research/hypotheses/${hypothesisId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildUpdatePayload(changes)),
  });
  if (!response.ok) {
    throw buildError("Failed to update hypothesis", response, null);
  }
  const payload = (await response.json()) as HypothesisApiResponse;
  return normalizeHypothesis(payload.hypothesis);
}

export const DEFAULT_FILTERS: HypothesisFilters = {
  statuses: [],
  minConfidence: undefined,
  query: undefined,
};
