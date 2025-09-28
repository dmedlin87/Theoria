import { getApiBaseUrl } from "./api";
import type { components } from "./generated/api";

function buildErrorMessage(status: number, body: string): string {
  if (body) {
    return body;
  }
  return `Request failed with status ${status}`;
}

async function handleResponse<T>(response: Response, parseJson: boolean): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(buildErrorMessage(response.status, body));
  }
  if (!parseJson) {
    return undefined as T;
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export type RequestOptions = RequestInit & { parseJson?: boolean };

export class TheoApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    const resolved = (baseUrl ?? getApiBaseUrl()).replace(/\/$/, "");
    this.baseUrl = resolved;
  }

  private async request<T>(path: string, init?: RequestOptions): Promise<T> {
    const { parseJson = true, headers, ...rest } = init ?? {};
    const response = await fetch(`${this.baseUrl}${path}`, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(headers ?? {}),
      },
      ...rest,
    });
    return handleResponse<T>(response, parseJson);
  }

  fetchFeatures(): Promise<Record<string, boolean>> {
    return this.request<Record<string, boolean>>("/features/");
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
    return this.request("/ai/sermon-prep/export?format=" + encodeURIComponent(payload.format), {
      method: "POST",
      body: JSON.stringify({
        model: payload.model,
        topic: payload.topic,
        osis: payload.osis ?? null,
      }),
    });
  }

  runTranscriptExport(payload: {
    documentId: string;
    format: string;
  }): Promise<import("../copilot/components/types").ExportPresetResult> {
    return this.request("/ai/transcript/export", {
      method: "POST",
      body: JSON.stringify({
        document_id: payload.documentId,
        format: payload.format,
      }),
    });
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
