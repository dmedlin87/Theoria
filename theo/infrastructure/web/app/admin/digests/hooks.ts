import { useCallback, useMemo, useRef, useState } from "react";

import type { TheoApiClient } from "../../lib/api-client";
import { createTheoApiClient } from "../../lib/api-client";
import type {
  CreateWatchlistPayload,
  TopicDigest,
  WatchlistResponse,
  WatchlistRunResponse,
  WatchlistUpdatePayload,
} from "./types";

function buildCommaList(values: string[] | null | undefined): string {
  return values?.join(", ") ?? "";
}

function splitCommaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function extractErrorMessage(unknownError: unknown): string {
  return unknownError instanceof Error ? unknownError.message : String(unknownError);
}

type TopicDigestState = {
  digest: TopicDigest | null;
  error: string | null;
  isLoading: boolean;
  isRefreshing: boolean;
  loadDigest: () => Promise<void>;
  refreshDigest: (hours: number) => Promise<void>;
  setError: (value: string | null) => void;
};

export function useTopicDigest(client?: TheoApiClient): TopicDigestState {
  const api = useMemo(() => client ?? createTheoApiClient(), [client]);
  const [digest, setDigest] = useState<TopicDigest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadDigest = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await api.getDigest();
      setDigest(payload);
    } catch (loadError) {
      setDigest(null);
      setError(extractErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  const refreshDigest = useCallback(
    async (hours: number) => {
      setIsRefreshing(true);
      setError(null);
      try {
        await api.refreshDigest(hours);
        const payload = await api.getDigest();
        setDigest(payload);
      } catch (refreshError) {
        setError(extractErrorMessage(refreshError));
      } finally {
        setIsRefreshing(false);
      }
    },
    [api],
  );

  return { digest, error, isLoading, isRefreshing, loadDigest, refreshDigest, setError };
}

type WatchlistCrudState = {
  watchlists: WatchlistResponse[];
  loadedFor: string | null;
  isLoading: boolean;
  error: string | null;
  loadWatchlists: (owner: string) => Promise<void>;
  editWatchlist: (id: string, updates: Partial<WatchlistResponse>) => void;
  saveWatchlist: (watchlist: WatchlistResponse) => Promise<void>;
  deleteWatchlist: (watchlistId: string) => Promise<void>;
  runWatchlist: (watchlistId: string, type: "preview" | "run") => Promise<WatchlistRunResponse>;
  createWatchlist: (payload: CreateWatchlistPayload) => Promise<void>;
  setError: (value: string | null) => void;
};

export function useWatchlistCrud(client?: TheoApiClient): WatchlistCrudState {
  const api = useMemo(() => client ?? createTheoApiClient(), [client]);
  const [watchlists, setWatchlists] = useState<WatchlistResponse[]>([]);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const watchlistOriginalsRef = useRef(new Map<string, WatchlistResponse>());
  const loadWatchlists = useCallback(
    async (owner: string) => {
      if (!owner) {
        setError("User ID is required to load watchlists");
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const payload = await api.listWatchlists(owner);
        watchlistOriginalsRef.current = new Map(payload.map((item) => [item.id, item]));
        setWatchlists(payload);
        setLoadedFor(owner);
      } catch (loadError) {
        setWatchlists([]);
        setLoadedFor(null);
        setError(extractErrorMessage(loadError));
      } finally {
        setIsLoading(false);
      }
    },
    [api],
  );

  const editWatchlist = useCallback((id: string, updates: Partial<WatchlistResponse>) => {
    setWatchlists((current) =>
      current.map((item) => (item.id === id ? { ...item, ...updates } : item)),
    );
  }, []);

  const createWatchlist = useCallback(
    async (payload: CreateWatchlistPayload) => {
      setError(null);
      const response = await api.createWatchlist(payload);
      watchlistOriginalsRef.current.set(response.id, response);
      setWatchlists((current) => [response, ...current]);
      setLoadedFor(payload.user_id);
    },
    [api],
  );

  const saveWatchlist = useCallback(
    async (watchlist: WatchlistResponse) => {
      const original = watchlistOriginalsRef.current.get(watchlist.id);
      if (!original) {
        return;
      }
      const payload: WatchlistUpdatePayload = {};
      if (watchlist.name !== original.name) {
        payload.name = watchlist.name;
      }
      if (watchlist.cadence !== original.cadence) {
        payload.cadence = watchlist.cadence;
      }
      if (watchlist.is_active !== original.is_active) {
        payload.is_active = watchlist.is_active;
      }
      if (buildCommaList(watchlist.delivery_channels) !== buildCommaList(original.delivery_channels)) {
        payload.delivery_channels = watchlist.delivery_channels;
      }
      const currentFilters = watchlist.filters ?? {};
      const originalFilters = original.filters ?? {};
      const filters: WatchlistUpdatePayload["filters"] = {};
      if (buildCommaList(currentFilters.topics ?? null) !== buildCommaList(originalFilters.topics ?? null)) {
        filters.topics = currentFilters.topics ?? [];
      }
      if (buildCommaList(currentFilters.keywords ?? null) !== buildCommaList(originalFilters.keywords ?? null)) {
        filters.keywords = currentFilters.keywords ?? [];
      }
      if (buildCommaList(currentFilters.authors ?? null) !== buildCommaList(originalFilters.authors ?? null)) {
        filters.authors = currentFilters.authors ?? [];
      }
      if (buildCommaList(currentFilters.osis ?? null) !== buildCommaList(originalFilters.osis ?? null)) {
        filters.osis = currentFilters.osis ?? [];
      }
      if (Object.keys(filters).length > 0) {
        payload.filters = filters;
      }
      if (Object.keys(payload).length === 0) {
        return;
      }
      setError(null);
      const response = await api.updateWatchlist(watchlist.id, payload);
      watchlistOriginalsRef.current.set(response.id, response);
      setWatchlists((current) => current.map((item) => (item.id === response.id ? response : item)));
    },
    [api],
  );

  const deleteWatchlist = useCallback(
    async (watchlistId: string) => {
      setError(null);
      await api.deleteWatchlist(watchlistId);
      watchlistOriginalsRef.current.delete(watchlistId);
      setWatchlists((current) => current.filter((item) => item.id !== watchlistId));
    },
    [api],
  );

  const runWatchlist = useCallback(
    async (watchlistId: string, type: "preview" | "run") => {
      setError(null);
      return api.runWatchlist(watchlistId, type);
    },
    [api],
  );

  return {
    watchlists,
    loadedFor,
    isLoading,
    error,
    loadWatchlists,
    editWatchlist,
    saveWatchlist,
    deleteWatchlist,
    runWatchlist,
    createWatchlist,
    setError,
  };
}

type WatchlistPaginationState = {
  showActiveOnly: boolean;
  setShowActiveOnly: (value: boolean) => void;
  page: number;
  setPage: (page: number) => void;
  paginated: WatchlistResponse[];
  totalPages: number;
  totalCount: number;
};

export function useWatchlistPagination(watchlists: WatchlistResponse[], pageSize: number): WatchlistPaginationState {
  const [showActiveOnly, setShowActiveOnly] = useState(false);
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!showActiveOnly) {
      return watchlists;
    }
    return watchlists.filter((item) => item.is_active);
  }, [showActiveOnly, watchlists]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const paginated = useMemo(
    () => filtered.slice(currentPage * pageSize, currentPage * pageSize + pageSize),
    [filtered, currentPage, pageSize],
  );

  return {
    showActiveOnly,
    setShowActiveOnly,
    page: currentPage,
    setPage,
    paginated,
    totalPages,
    totalCount: filtered.length,
  };
}

  type WatchlistEventState = {
    events: WatchlistRunResponse[];
    eventsLoading: boolean;
    eventsError: string | null;
    eventsWatchlistId: string | null;
    loadEvents: (watchlistId: string, since: string) => Promise<void>;
    cancelEventsRequest: () => void;
  };

  export function useWatchlistEvents(client?: TheoApiClient): WatchlistEventState {
    const api = useMemo(() => client ?? createTheoApiClient(), [client]);
    const [events, setEvents] = useState<WatchlistRunResponse[]>([]);
    const [eventsLoading, setEventsLoading] = useState(false);
    const [eventsError, setEventsError] = useState<string | null>(null);
    const [eventsWatchlistId, setEventsWatchlistId] = useState<string | null>(null);
    const eventsRequestTokenRef = useRef(0);

    const cancelEventsRequest = useCallback(() => {
      eventsRequestTokenRef.current += 1;
      setEventsLoading(false);
    }, []);

    const loadEvents = useCallback(
      async (watchlistId: string, since: string) => {
        const requestToken = eventsRequestTokenRef.current + 1;
        eventsRequestTokenRef.current = requestToken;

        setEventsLoading(true);
        if (eventsRequestTokenRef.current === requestToken) {
          setEvents([]);
          setEventsError(null);
        }
        try {
          const payload = await api.fetchWatchlistEvents(watchlistId, since);
          if (eventsRequestTokenRef.current === requestToken) {
            setEvents(payload);
            setEventsWatchlistId(watchlistId);
          }
        } catch (eventsError) {
          if (eventsRequestTokenRef.current === requestToken) {
            setEventsError(extractErrorMessage(eventsError));
            setEventsWatchlistId(watchlistId);
          }
        } finally {
          if (eventsRequestTokenRef.current === requestToken) {
            setEventsLoading(false);
          }
        }
      },
      [api],
    );

    return {
      events,
      eventsLoading,
      eventsError,
      eventsWatchlistId,
      loadEvents,
      cancelEventsRequest,
    };
  }

type CommaListHelpers = {
  toCommaList: (values: string[] | null | undefined) => string;
  fromCommaList: (value: string) => string[];
};

export function useCommaListHelpers(): CommaListHelpers {
  return {
    toCommaList: buildCommaList,
    fromCommaList: splitCommaList,
  };
}
