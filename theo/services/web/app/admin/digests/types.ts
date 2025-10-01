export type TopicCluster = {
  topic: string;
  new_documents: number;
  total_documents: number;
  document_ids: string[];
};

export type TopicDigest = {
  generated_at: string;
  window_start: string;
  topics: TopicCluster[];
};

export type WatchlistFilters = {
  osis?: string[] | null;
  keywords?: string[] | null;
  authors?: string[] | null;
  topics?: string[] | null;
  metadata?: Record<string, unknown> | null;
};

export type WatchlistResponse = {
  id: string;
  user_id: string;
  name: string;
  filters: WatchlistFilters;
  cadence: string;
  delivery_channels: string[];
  is_active: boolean;
  last_run: string | null;
  created_at: string;
  updated_at: string;
};

export type WatchlistMatch = {
  document_id: string;
  passage_id: string | null;
  osis: string | null;
  snippet: string | null;
  reasons: string[] | null;
};

export type WatchlistRunResponse = {
  id: string | null;
  watchlist_id: string;
  run_started: string;
  run_completed: string;
  window_start: string;
  matches: WatchlistMatch[];
  document_ids: string[];
  passage_ids: string[];
  delivery_status: string | null;
  error: string | null;
};

export type CreateWatchlistPayload = {
  user_id: string;
  name: string;
  cadence: string;
  delivery_channels: string[];
  filters: WatchlistFilters;
};

export type WatchlistUpdatePayload = {
  name?: string;
  filters?: WatchlistFilters;
  cadence?: string;
  delivery_channels?: string[];
  is_active?: boolean;
};
