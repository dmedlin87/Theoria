import type { components } from "./generated/api";
import type { HybridSearchFilters } from "./guardrails";
import {
  ChatSessionState,
  ResearchPlan,
  ResearchPlanStepStatus,
  normaliseExportResponse,
  normaliseResearchPlan,
} from "./api-normalizers";
import { ChatWorkflowOptions, ChatWorkflowRequest, ChatWorkflowResult, createChatClient } from "./chat-client";
import { createHttpClient } from "./http";

export type { HybridSearchFilters } from "./guardrails";
export type {
  ChatSessionMemoryEntry,
  ChatSessionPreferencesPayload,
  ChatSessionState,
} from "./api-normalizers";
export type { ResearchPlan, ResearchPlanStepStatus } from "./api-normalizers";
export type {
  ChatWorkflowClient,
  ChatWorkflowGuardrail,
  ChatWorkflowMessage,
  ChatWorkflowOptions,
  ChatWorkflowRequest,
  ChatWorkflowResult,
  ChatWorkflowStreamEvent,
  ChatWorkflowSuccess,
} from "./chat-client";
export { TheoApiError, NetworkError } from "./http";

type ExportDeliverableResponse = components["schemas"]["ExportDeliverableResponse"];
export type ProviderSettingsRequest = components["schemas"]["ProviderSettingsRequest"];
export type ProviderSettingsResponse = components["schemas"]["ProviderSettingsResponse"];

export type PerspectiveCitation = {
  document_id?: string | null;
  document_title?: string | null;
  osis?: string | null;
  snippet: string;
  rank?: number | null;
  score?: number | null;
};

export type PerspectiveView = {
  perspective: "skeptical" | "apologetic" | "neutral";
  answer: string;
  confidence: number;
  key_claims: string[];
  citations: PerspectiveCitation[];
};

export type PerspectiveSynthesisPayload = {
  question: string;
  top_k?: number;
  filters?: HybridSearchFilters | null;
};

export type PerspectiveSynthesisResult = {
  question: string;
  consensus_points: string[];
  tension_map: Record<string, string[]>;
  meta_analysis: string;
  perspective_views: Record<string, PerspectiveView>;
};

type VerseResponse = import("../copilot/components/types").VerseResponse;
type SermonResponse = import("../copilot/components/types").SermonResponse;
type ComparativeResponse = import("../copilot/components/types").ComparativeResponse;
type MultimediaDigestResponse = import("../copilot/components/types").MultimediaDigestResponse;
type DevotionalResponse = import("../copilot/components/types").DevotionalResponse;
type CollaborationResponse = import("../copilot/components/types").CollaborationResponse;
type CorpusCurationReport = import("../copilot/components/types").CorpusCurationReport;
type ExportPresetResult = import("../copilot/components/types").ExportPresetResult;
type CitationExportResponse = import("../copilot/components/types").CitationExportResponse;
type TopicDigest = import("../admin/digests/types").TopicDigest;
type WatchlistResponse = import("../admin/digests/types").WatchlistResponse;
type CreateWatchlistPayload = import("../admin/digests/types").CreateWatchlistPayload;
type WatchlistUpdatePayload = import("../admin/digests/types").WatchlistUpdatePayload;
type WatchlistRunResponse = import("../admin/digests/types").WatchlistRunResponse;

type TheoApiClientShape = {
  fetchFeatures(): Promise<Record<string, boolean>>;
  runChatWorkflow(payload: ChatWorkflowRequest, options?: ChatWorkflowOptions): Promise<ChatWorkflowResult>;
  fetchChatSession(sessionId: string): Promise<ChatSessionState | null>;
  fetchResearchPlan(sessionId: string): Promise<ResearchPlan | null>;
  reorderResearchPlan(sessionId: string, order: string[]): Promise<ResearchPlan>;
  updateResearchPlanStep(
    sessionId: string,
    stepId: string,
    payload: ResearchPlanStepUpdatePayload,
  ): Promise<ResearchPlan>;
  skipResearchPlanStep(
    sessionId: string,
    stepId: string,
    payload: ResearchPlanStepSkipPayload,
  ): Promise<ResearchPlan>;
  runVerseWorkflow(payload: { model: string; osis?: string | null; passage?: string | null; question?: string | null }): Promise<VerseResponse>;
  runSermonWorkflow(payload: { model: string; topic: string; osis?: string | null }): Promise<SermonResponse>;
  runComparativeWorkflow(payload: { model: string; osis: string; participants: string[] }): Promise<ComparativeResponse>;
  runMultimediaWorkflow(payload: { model: string; collection?: string | null }): Promise<MultimediaDigestResponse>;
  runDevotionalWorkflow(payload: { model: string; osis: string; focus: string }): Promise<DevotionalResponse>;
  runCollaborationWorkflow(payload: {
    model: string;
    thread: string;
    osis: string;
    viewpoints: string[];
  }): Promise<CollaborationResponse>;
  runCurationWorkflow(payload: { model: string; since?: string | null }): Promise<CorpusCurationReport>;
  runPerspectiveSynthesis(payload: PerspectiveSynthesisPayload): Promise<PerspectiveSynthesisResult>;
  runSermonExport(payload: { model: string; topic: string; osis?: string | null; format: string }): Promise<ExportPresetResult>;
  runTranscriptExport(payload: { documentId: string; format: string }): Promise<ExportPresetResult>;
  exportCitations(payload: components["schemas"]["CitationExportRequest"]): Promise<CitationExportResponse>;
  getDigest(): Promise<TopicDigest>;
  refreshDigest(hours: number): Promise<TopicDigest>;
  listWatchlists(userId: string): Promise<WatchlistResponse[]>;
  createWatchlist(payload: CreateWatchlistPayload): Promise<WatchlistResponse>;
  updateWatchlist(watchlistId: string, payload: WatchlistUpdatePayload): Promise<WatchlistResponse>;
  deleteWatchlist(watchlistId: string): Promise<void>;
  runWatchlist(watchlistId: string, type: "preview" | "run"): Promise<WatchlistRunResponse>;
  fetchWatchlistEvents(watchlistId: string, since?: string): Promise<WatchlistRunResponse[]>;
  listProviderSettings(): Promise<ProviderSettingsResponse[]>;
  getProviderSettings(provider: string): Promise<ProviderSettingsResponse>;
  upsertProviderSettings(
    provider: string,
    payload: ProviderSettingsRequest,
  ): Promise<ProviderSettingsResponse>;
  deleteProviderSettings(provider: string): Promise<void>;
};

export type ResearchPlanStepUpdatePayload = {
  query?: string | null;
  tool?: string | null;
  status?: ResearchPlanStepStatus | null;
  estimatedTokens?: number | null;
  estimatedCostUsd?: number | null;
  estimatedDurationSeconds?: number | null;
  metadata?: Record<string, unknown> | null;
};

export type ResearchPlanStepSkipPayload = {
  reason?: string | null;
};

export function createTheoApiClient(baseUrl?: string): TheoApiClientShape {
  const http = createHttpClient(baseUrl);
  const chat = createChatClient(http);
  const request = http.request;

  return {
    ...chat,
    fetchFeatures(): Promise<Record<string, boolean>> {
      return request<Record<string, boolean>>("/features/");
    },
    async fetchResearchPlan(sessionId: string): Promise<ResearchPlan | null> {
      const payload = await request(`/ai/chat/${encodeURIComponent(sessionId)}/plan`);
      return normaliseResearchPlan(payload);
    },
    async reorderResearchPlan(sessionId, order) {
      const payload = await request(`/ai/chat/${encodeURIComponent(sessionId)}/plan/order`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order }),
      });
      const plan = normaliseResearchPlan(payload);
      if (!plan) {
        throw new Error("Failed to parse research plan response");
      }
      return plan;
    },
    async updateResearchPlanStep(sessionId, stepId, payload) {
      const body: Record<string, unknown> = {};
      if (payload.query !== undefined) {
        body.query = payload.query;
      }
      if (payload.tool !== undefined) {
        body.tool = payload.tool;
      }
      if (payload.status !== undefined) {
        body.status = payload.status;
      }
      if (payload.estimatedTokens !== undefined) {
        body.estimated_tokens = payload.estimatedTokens;
      }
      if (payload.estimatedCostUsd !== undefined) {
        body.estimated_cost_usd = payload.estimatedCostUsd;
      }
      if (payload.estimatedDurationSeconds !== undefined) {
        body.estimated_duration_seconds = payload.estimatedDurationSeconds;
      }
      if (payload.metadata !== undefined) {
        body.metadata = payload.metadata;
      }
      const responsePayload = await request(
        `/ai/chat/${encodeURIComponent(sessionId)}/plan/steps/${encodeURIComponent(stepId)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      const plan = normaliseResearchPlan(responsePayload);
      if (!plan) {
        throw new Error("Failed to parse research plan response");
      }
      return plan;
    },
    async skipResearchPlanStep(sessionId, stepId, payload) {
      const responsePayload = await request(
        `/ai/chat/${encodeURIComponent(sessionId)}/plan/steps/${encodeURIComponent(stepId)}/skip`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: payload.reason ?? null }),
        },
      );
      const plan = normaliseResearchPlan(responsePayload);
      if (!plan) {
        throw new Error("Failed to parse research plan response");
      }
      return plan;
    },
    runVerseWorkflow(payload) {
      return request<VerseResponse>("/ai/verse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    runSermonWorkflow(payload) {
      return request<SermonResponse>("/ai/sermon-prep", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    runComparativeWorkflow(payload) {
      return request<ComparativeResponse>("/ai/comparative", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    runMultimediaWorkflow(payload) {
      return request<MultimediaDigestResponse>("/ai/multimedia", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    runDevotionalWorkflow(payload) {
      return request<DevotionalResponse>("/ai/devotional", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    runCollaborationWorkflow(payload) {
      return request<CollaborationResponse>("/ai/collaboration", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    runCurationWorkflow(payload) {
      return request<CorpusCurationReport>("/ai/curation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    runPerspectiveSynthesis(payload) {
      return request<PerspectiveSynthesisResult>("/ai/perspectives", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    runSermonExport(payload) {
      return request<ExportDeliverableResponse>(
        `/ai/sermon-prep/export?format=${encodeURIComponent(payload.format)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: payload.model,
            topic: payload.topic,
            osis: payload.osis ?? null,
          }),
        },
      ).then(normaliseExportResponse);
    },
    runTranscriptExport(payload) {
      return request<ExportDeliverableResponse>("/ai/transcript/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: payload.documentId,
          format: payload.format,
        }),
      }).then(normaliseExportResponse);
    },
    exportCitations(payload) {
      return request<CitationExportResponse>("/ai/citations/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    getDigest() {
      return request<TopicDigest>("/ai/digest");
    },
    refreshDigest(hours) {
      return request<TopicDigest>(`/ai/digest?hours=${hours}`, {
        method: "POST",
      });
    },
    listWatchlists(userId) {
      return request<WatchlistResponse[]>(
        `/ai/digest/watchlists?user_id=${encodeURIComponent(userId)}`,
      );
    },
    createWatchlist(payload) {
      return request<WatchlistResponse>("/ai/digest/watchlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    updateWatchlist(watchlistId, payload) {
      return request<WatchlistResponse>(`/ai/digest/watchlists/${watchlistId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    deleteWatchlist(watchlistId) {
      return request(`/ai/digest/watchlists/${watchlistId}`, {
        method: "DELETE",
        parseJson: false,
      });
    },
    runWatchlist(watchlistId, type) {
      const path =
        type === "preview"
          ? `/ai/digest/watchlists/${watchlistId}/preview`
          : `/ai/digest/watchlists/${watchlistId}/run`;
      const method = type === "preview" ? "GET" : "POST";
      return request<WatchlistRunResponse>(path, { method });
    },
    fetchWatchlistEvents(watchlistId, since) {
      const query = since ? `?since=${encodeURIComponent(since)}` : "";
      return request<WatchlistRunResponse[]>(
        `/ai/digest/watchlists/${watchlistId}/events${query}`,
      );
    },
    listProviderSettings() {
      return request<ProviderSettingsResponse[]>("/settings/ai/providers");
    },
    getProviderSettings(provider) {
      return request<ProviderSettingsResponse>(`/settings/ai/providers/${provider}`);
    },
    upsertProviderSettings(provider, payload) {
      return request<ProviderSettingsResponse>(`/settings/ai/providers/${provider}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    },
    deleteProviderSettings(provider) {
      return request(`/settings/ai/providers/${provider}`, {
        method: "DELETE",
        parseJson: false,
      });
    },
  } satisfies TheoApiClientShape;
}

export type TheoApiClient = TheoApiClientShape;
