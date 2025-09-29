import { getApiBaseUrl } from "./api";
import type { components } from "./generated/api";

type ExportDeliverableResponse = components["schemas"]["ExportDeliverableResponse"];
type HybridSearchFilters = components["schemas"]["HybridSearchFilters"];
type RAGAnswer = components["schemas"]["RAGAnswer"];

export type ChatSessionMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type ChatSessionPreferences = {
  mode?: string | null;
  default_filters?: HybridSearchFilters | null;
  frequently_opened_panels?: string[] | null;
};

export type ChatSessionResponse = {
  session_id: string;
  message: ChatSessionMessage;
  answer: RAGAnswer;
};

export type ChatSessionState = {
  session_id: string;
  summary?: string | null;
  stance?: string | null;
  linked_document_ids: string[];
  memory_snippets: string[];
  preferences?: ChatSessionPreferences | null;
  created_at: string;
  updated_at: string;
  last_turn_at?: string | null;
};

export type ChatTurnRequest = {
  messages: ChatSessionMessage[];
  sessionId?: string | null;
  model?: string | null;
  osis?: string | null;
  filters?: Partial<HybridSearchFilters> | null;
  preferences?: ChatSessionPreferences | null;
};

function normaliseExportResponse(
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

function buildErrorMessage(status: number, body: string): string {
  if (body) {
    return body;
  }
  return `Request failed with status ${status}`;
}

async function handleResponse(
  response: Response,
  parseJson: false,
): Promise<void>;
async function handleResponse<T>(
  response: Response,
  parseJson: true,
): Promise<T>;
async function handleResponse<T>(
  response: Response,
  parseJson: boolean,
): Promise<T | void>;
async function handleResponse<T>(
  response: Response,
  parseJson: boolean,
): Promise<T | void> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(buildErrorMessage(response.status, body));
  }
  if (!parseJson) {
    return;
  }
  if (response.status === 204) {
    return;
  }
  const data = (await response.json()) as unknown;
  // The generated OpenAPI types describe the JSON schema for this response.
  return data as T;
}

export type RequestOptions = RequestInit & { parseJson?: boolean };

export class TheoApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    const resolved = (baseUrl ?? getApiBaseUrl()).replace(/\/$/, "");
    this.baseUrl = resolved;
  }

  private async request(path: string, init: RequestOptions & { parseJson: false }): Promise<void>;
  private async request<T>(
    path: string,
    init?: RequestOptions & { parseJson?: true },
  ): Promise<T>;
  private async request<T>(path: string, init?: RequestOptions): Promise<T | void> {
    const { parseJson = true, headers, ...rest } = init ?? {};
    const response = await fetch(`${this.baseUrl}${path}`, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(headers ?? {}),
      },
      ...rest,
    });
    if (parseJson) {
      return handleResponse<T>(response, true);
    }
    return handleResponse(response, false);
  }

  fetchFeatures(): Promise<Record<string, boolean>> {
    return this.request<Record<string, boolean>>("/features/");
  }

  runChatTurn(payload: ChatTurnRequest): Promise<ChatSessionResponse> {
    const body: Record<string, unknown> = {
      messages: payload.messages,
    };
    if (payload.sessionId) {
      body.session_id = payload.sessionId;
    }
    if (payload.model) {
      body.model = payload.model;
    }
    if (payload.osis) {
      body.osis = payload.osis;
    }
    if (payload.filters) {
      body.filters = payload.filters;
    }
    if (payload.preferences) {
      body.preferences = payload.preferences;
    }
    return this.request("/ai/chat", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  fetchChatSession(sessionId: string): Promise<ChatSessionState> {
    return this.request(`/ai/chat/${encodeURIComponent(sessionId)}`);
  }

  runVerseWorkflow(payload: {
    model: string;
    osis?: string | null;
    passage?: string | null;
    question?: string | null;
  }): Promise<import("../copilot/components/types").VerseResponse> {
    return this.request("/ai/verse", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runSermonWorkflow(payload: {
    model: string;
    topic: string;
    osis?: string | null;
  }): Promise<import("../copilot/components/types").SermonResponse> {
    return this.request("/ai/sermon-prep", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runComparativeWorkflow(payload: {
    model: string;
    osis: string;
    participants: string[];
  }): Promise<import("../copilot/components/types").ComparativeResponse> {
    return this.request("/ai/comparative", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runMultimediaWorkflow(payload: {
    model: string;
    collection?: string | null;
  }): Promise<import("../copilot/components/types").MultimediaDigestResponse> {
    return this.request("/ai/multimedia", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runDevotionalWorkflow(payload: {
    model: string;
    osis: string;
    focus: string;
  }): Promise<import("../copilot/components/types").DevotionalResponse> {
    return this.request("/ai/devotional", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runCollaborationWorkflow(payload: {
    model: string;
    thread: string;
    osis: string;
    viewpoints: string[];
  }): Promise<import("../copilot/components/types").CollaborationResponse> {
    return this.request("/ai/collaboration", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runCurationWorkflow(payload: {
    model: string;
    since?: string | null;
  }): Promise<import("../copilot/components/types").CorpusCurationReport> {
    return this.request("/ai/curation", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runSermonExport(payload: {
    model: string;
    topic: string;
    osis?: string | null;
    format: string;
  }): Promise<import("../copilot/components/types").ExportPresetResult> {
    return this.request<ExportDeliverableResponse>(
      "/ai/sermon-prep/export?format=" + encodeURIComponent(payload.format),
      {
        method: "POST",
        body: JSON.stringify({
          model: payload.model,
          topic: payload.topic,
          osis: payload.osis ?? null,
        }),
      },
    ).then(normaliseExportResponse);
  }

  runTranscriptExport(payload: {
    documentId: string;
    format: string;
  }): Promise<import("../copilot/components/types").ExportPresetResult> {
    return this.request<ExportDeliverableResponse>("/ai/transcript/export", {
      method: "POST",
      body: JSON.stringify({
        document_id: payload.documentId,
        format: payload.format,
      }),
    }).then(normaliseExportResponse);
  }

  exportCitations(
    payload: components["schemas"]["CitationExportRequest"],
  ): Promise<import("../copilot/components/types").CitationExportResponse> {
    return this.request("/ai/citations/export", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  getDigest(): Promise<import("../admin/digests/types").TopicDigest> {
    return this.request("/ai/digest");
  }

  refreshDigest(hours: number): Promise<import("../admin/digests/types").TopicDigest> {
    return this.request(`/ai/digest?hours=${hours}`, {
      method: "POST",
    });
  }

  listWatchlists(userId: string): Promise<import("../admin/digests/types").WatchlistResponse[]> {
    return this.request(`/ai/digest/watchlists?user_id=${encodeURIComponent(userId)}`);
  }

  createWatchlist(payload: import("../admin/digests/types").CreateWatchlistPayload): Promise<
    import("../admin/digests/types").WatchlistResponse
  > {
    return this.request("/ai/digest/watchlists", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  updateWatchlist(
    watchlistId: string,
    payload: import("../admin/digests/types").WatchlistUpdatePayload,
  ): Promise<import("../admin/digests/types").WatchlistResponse> {
    return this.request(`/ai/digest/watchlists/${watchlistId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  deleteWatchlist(watchlistId: string): Promise<void> {
    return this.request(`/ai/digest/watchlists/${watchlistId}`, {
      method: "DELETE",
      parseJson: false,
    });
  }

  runWatchlist(
    watchlistId: string,
    type: "preview" | "run",
  ): Promise<import("../admin/digests/types").WatchlistRunResponse> {
    const path =
      type === "preview"
        ? `/ai/digest/watchlists/${watchlistId}/preview`
        : `/ai/digest/watchlists/${watchlistId}/run`;
    const method = type === "preview" ? "GET" : "POST";
    return this.request(path, { method });
  }

  fetchWatchlistEvents(
    watchlistId: string,
    since?: string,
  ): Promise<import("../admin/digests/types").WatchlistRunResponse[]> {
    const query = since ? `?since=${encodeURIComponent(since)}` : "";
    return this.request(`/ai/digest/watchlists/${watchlistId}/events${query}`);
  }
}

export function createTheoApiClient(baseUrl?: string): TheoApiClient {
  return new TheoApiClient(baseUrl);
}
