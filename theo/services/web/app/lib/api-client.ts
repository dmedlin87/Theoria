import type { components } from "./generated/api";
import { ChatSessionState, normaliseExportResponse } from "./api-normalizers";
import { ChatWorkflowOptions, ChatWorkflowRequest, ChatWorkflowResult, createChatClient } from "./chat-client";
import { createHttpClient } from "./http";

export type { HybridSearchFilters } from "./guardrails";
export type { ChatSessionMemoryEntry, ChatSessionPreferencesPayload, ChatSessionState } from "./api-normalizers";
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
export { TheoApiError } from "./http";

type ExportDeliverableResponse = components["schemas"]["ExportDeliverableResponse"];

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
    runVerseWorkflow(payload) {
      return request<VerseResponse>("/ai/verse", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    runSermonWorkflow(payload) {
      return request<SermonResponse>("/ai/sermon-prep", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    runComparativeWorkflow(payload) {
      return request<ComparativeResponse>("/ai/comparative", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    runMultimediaWorkflow(payload) {
      return request<MultimediaDigestResponse>("/ai/multimedia", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    runDevotionalWorkflow(payload) {
      return request<DevotionalResponse>("/ai/devotional", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    runCollaborationWorkflow(payload) {
      return request<CollaborationResponse>("/ai/collaboration", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    runCurationWorkflow(payload) {
      return request<CorpusCurationReport>("/ai/curation", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    runSermonExport(payload) {
      return request<ExportDeliverableResponse>(
        `/ai/sermon-prep/export?format=${encodeURIComponent(payload.format)}`,
        {
          method: "POST",
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
        body: JSON.stringify({
          document_id: payload.documentId,
          format: payload.format,
        }),
      }).then(normaliseExportResponse);
    },
    exportCitations(payload) {
      return request<CitationExportResponse>("/ai/citations/export", {
        method: "POST",
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
        body: JSON.stringify(payload),
      });
    },
    updateWatchlist(watchlistId, payload) {
      return request<WatchlistResponse>(`/ai/digest/watchlists/${watchlistId}`, {
        method: "PATCH",
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
  } satisfies TheoApiClientShape;
}

export type TheoApiClient = TheoApiClientShape;
