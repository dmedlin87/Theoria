"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getApiBaseUrl } from "../../lib/api";

type TopicCluster = {
  topic: string;
  summary: string | null;
  new_documents: number;
  total_documents: number;
  document_ids: string[];
};

type TopicDigest = {
  generated_at: string;
  window_start: string;
  topics: TopicCluster[];
};

type WatchlistFilters = {
  keywords?: string[] | null;
  authors?: string[] | null;
  topics?: string[] | null;
  metadata?: Record<string, unknown> | null;
};

type WatchlistResponse = {
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

type WatchlistMatch = {
  document_id: string;
  passage_id: string | null;
  osis: string | null;
  snippet: string | null;
  reasons: string[] | null;
};

type WatchlistRunResponse = {
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

type WatchlistUpdatePayload = {
  name?: string;
  filters?: WatchlistFilters;
  cadence?: string;
  delivery_channels?: string[];
  is_active?: boolean;
};

const PAGE_SIZE = 5;

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Date(value).toLocaleString();
  } catch (error) {
    return value;
  }
}

function commaList(values: string[] | null | undefined): string {
  return values?.join(", ") ?? "";
}

function parseCommaList(value: string): string[] | undefined {
  const trimmed = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return trimmed.length ? trimmed : undefined;
}

function buildErrorMessage(status: number, body: string): string {
  if (body) {
    return body;
  }
  return `Request failed with status ${status}`;
}

export default function DigestDashboard(): JSX.Element {
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const [digest, setDigest] = useState<TopicDigest | null>(null);
  const [digestError, setDigestError] = useState<string | null>(null);
  const [isDigestLoading, setIsDigestLoading] = useState(false);
  const [refreshHours, setRefreshHours] = useState("168");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [userId, setUserId] = useState("");
  const [watchlists, setWatchlists] = useState<WatchlistResponse[]>([]);
  const watchlistOriginalsRef = useRef(new Map<string, WatchlistResponse>());
  const [watchlistsLoadedFor, setWatchlistsLoadedFor] = useState<string | null>(null);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [isWatchlistLoading, setIsWatchlistLoading] = useState(false);
  const [showActiveOnly, setShowActiveOnly] = useState(false);
  const [watchlistPage, setWatchlistPage] = useState(0);

  const [creationName, setCreationName] = useState("");
  const [creationCadence, setCreationCadence] = useState("daily");
  const [creationDeliveryChannels, setCreationDeliveryChannels] = useState("in_app");
  const [creationTopics, setCreationTopics] = useState("");
  const [creationKeywords, setCreationKeywords] = useState("");
  const [creationAuthors, setCreationAuthors] = useState("");
  const [creationError, setCreationError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const [lastRunResult, setLastRunResult] = useState<WatchlistRunResponse | null>(null);
  const [lastRunType, setLastRunType] = useState<"preview" | "run" | null>(null);
  const [lastRunError, setLastRunError] = useState<string | null>(null);

  const [events, setEvents] = useState<WatchlistRunResponse[]>([]);
  const [eventsWatchlistId, setEventsWatchlistId] = useState<string | null>(null);
  const [eventsSince, setEventsSince] = useState("");
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [eventsLoading, setEventsLoading] = useState(false);

  const request = useCallback(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const response = await fetch(`${baseUrl}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(init?.headers ?? {}),
        },
        cache: "no-store",
      });
      if (!response.ok) {
        const body = await response.text();
        throw new Error(buildErrorMessage(response.status, body));
      }
      return (await response.json()) as T;
    },
    [baseUrl],
  );

  const loadDigest = useCallback(async () => {
    setIsDigestLoading(true);
    setDigestError(null);
    try {
      const payload = await request<TopicDigest>(`/ai/digest`);
      setDigest(payload);
    } catch (error) {
      setDigest(null);
      setDigestError((error as Error).message);
    } finally {
      setIsDigestLoading(false);
    }
  }, [request]);

  useEffect(() => {
    void loadDigest();
  }, [loadDigest]);

  const refreshDigest = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const hours = Number.parseInt(refreshHours, 10);
      if (!Number.isFinite(hours) || hours <= 0) {
        setDigestError("Hours must be a positive number");
        return;
      }
      setIsRefreshing(true);
      setDigestError(null);
      try {
        await request<TopicDigest>(`/ai/digest?hours=${hours}`, { method: "POST" });
        await loadDigest();
      } catch (error) {
        setDigestError((error as Error).message);
      } finally {
        setIsRefreshing(false);
      }
    },
    [refreshHours, request, loadDigest],
  );

  const loadWatchlists = useCallback(
    async (owner: string) => {
      if (!owner) {
        setWatchlistError("User ID is required to load watchlists");
        return;
      }
      setIsWatchlistLoading(true);
      setWatchlistError(null);
      try {
        const payload = await request<WatchlistResponse[]>(
          `/ai/digest/watchlists?user_id=${encodeURIComponent(owner)}`,
        );
        watchlistOriginalsRef.current = new Map(payload.map((item) => [item.id, item]));
        setWatchlists(payload);
        setWatchlistsLoadedFor(owner);
        setWatchlistPage(0);
      } catch (error) {
        setWatchlists([]);
        setWatchlistsLoadedFor(null);
        setWatchlistError((error as Error).message);
      } finally {
        setIsWatchlistLoading(false);
      }
    },
    [request],
  );

  const handleCreateWatchlist = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!userId) {
        setCreationError("User ID is required to create a watchlist");
        return;
      }
      if (!creationName.trim()) {
        setCreationError("Name is required");
        return;
      }
      setCreationError(null);
      setIsCreating(true);
      try {
        const payload = await request<WatchlistResponse>(`/ai/digest/watchlists`, {
          method: "POST",
          body: JSON.stringify({
            user_id: userId.trim(),
            name: creationName.trim(),
            cadence: creationCadence,
            delivery_channels: creationDeliveryChannels
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
            filters: {
              topics: parseCommaList(creationTopics) ?? null,
              keywords: parseCommaList(creationKeywords) ?? null,
              authors: parseCommaList(creationAuthors) ?? null,
            },
          }),
        });
        watchlistOriginalsRef.current.set(payload.id, payload);
        setWatchlists((current) => [payload, ...current]);
        setCreationName("");
        setCreationTopics("");
        setCreationKeywords("");
        setCreationAuthors("");
      } catch (error) {
        setCreationError((error as Error).message);
      } finally {
        setIsCreating(false);
      }
    },
    [creationAuthors, creationCadence, creationDeliveryChannels, creationKeywords, creationName, creationTopics, request, userId],
  );

  const updateWatchlist = useCallback(
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
      if (
        commaList(watchlist.delivery_channels) !== commaList(original.delivery_channels)
      ) {
        payload.delivery_channels = watchlist.delivery_channels;
      }
      const currentFilters = watchlist.filters ?? {};
      const originalFilters = original.filters ?? {};
      const filters: WatchlistFilters = {};
      if (commaList(currentFilters.topics ?? null) !== commaList(originalFilters.topics ?? null)) {
        filters.topics = currentFilters.topics ?? [];
      }
      if (
        commaList(currentFilters.keywords ?? null) !== commaList(originalFilters.keywords ?? null)
      ) {
        filters.keywords = currentFilters.keywords ?? [];
      }
      if (commaList(currentFilters.authors ?? null) !== commaList(originalFilters.authors ?? null)) {
        filters.authors = currentFilters.authors ?? [];
      }
      if (Object.keys(filters).length > 0) {
        payload.filters = filters;
      }
      if (Object.keys(payload).length === 0) {
        return;
      }
      try {
        setWatchlistError(null);
        const response = await request<WatchlistResponse>(
          `/ai/digest/watchlists/${watchlist.id}`,
          {
            method: "PATCH",
            body: JSON.stringify(payload),
          },
        );
        watchlistOriginalsRef.current.set(response.id, response);
        setWatchlists((current) =>
          current.map((item) => (item.id === response.id ? response : item)),
        );
      } catch (error) {
        setWatchlistError((error as Error).message);
      }
    },
    [request],
  );

  const deleteWatchlist = useCallback(
    async (watchlistId: string) => {
      setWatchlistError(null);
      try {
        const response = await fetch(`${baseUrl}/ai/digest/watchlists/${watchlistId}`, {
          method: "DELETE",
          cache: "no-store",
        });
        if (!response.ok) {
          const body = await response.text();
          throw new Error(buildErrorMessage(response.status, body));
        }
        watchlistOriginalsRef.current.delete(watchlistId);
        setWatchlists((current) => current.filter((item) => item.id !== watchlistId));
      } catch (error) {
        setWatchlistError((error as Error).message);
      }
    },
    [baseUrl],
  );

  const runWatchlist = useCallback(
    async (watchlistId: string, type: "preview" | "run") => {
      setLastRunResult(null);
      setLastRunType(null);
      setLastRunError(null);
      try {
        const path =
          type === "preview"
            ? `/ai/digest/watchlists/${watchlistId}/preview`
            : `/ai/digest/watchlists/${watchlistId}/run`;
        const init: RequestInit =
          type === "preview"
            ? { method: "GET" }
            : { method: "POST" };
        const result = await request<WatchlistRunResponse>(path, init);
        setLastRunType(type);
        setLastRunResult(result);
        setLastRunError(null);
      } catch (error) {
        setLastRunError((error as Error).message);
      }
    },
    [request],
  );

  const loadEvents = useCallback(
    async (watchlistId: string, since: string) => {
      setEvents([]);
      setEventsError(null);
      setEventsLoading(true);
      try {
        const query = since ? `?since=${encodeURIComponent(since)}` : "";
        const payload = await request<WatchlistRunResponse[]>(
          `/ai/digest/watchlists/${watchlistId}/events${query}`,
        );
        setEvents(payload);
        setEventsWatchlistId(watchlistId);
      } catch (error) {
        setEventsError((error as Error).message);
        setEventsWatchlistId(watchlistId);
      } finally {
        setEventsLoading(false);
      }
    },
    [request],
  );

  const filteredWatchlists = useMemo(() => {
    if (!showActiveOnly) {
      return watchlists;
    }
    return watchlists.filter((item) => item.is_active);
  }, [watchlists, showActiveOnly]);

  const totalPages = Math.max(1, Math.ceil(filteredWatchlists.length / PAGE_SIZE));
  const activePage = Math.min(watchlistPage, totalPages - 1);
  const paginatedWatchlists = filteredWatchlists.slice(
    activePage * PAGE_SIZE,
    activePage * PAGE_SIZE + PAGE_SIZE,
  );

  useEffect(() => {
    setWatchlistPage((current) => Math.min(current, totalPages - 1));
  }, [totalPages]);

  const digestTopics = digest?.topics ?? [];

  return (
    <div className="stack" style={{ gap: "2rem" }}>
      <section aria-labelledby="digest-overview">
        <header className="cluster" style={{ justifyContent: "space-between", gap: "1rem" }}>
          <div>
            <h1 id="digest-overview">Topic digests</h1>
            <p>
              View the latest topical activity across the corpus and trigger a new digest run.
            </p>
          </div>
          <form className="cluster" onSubmit={refreshDigest} style={{ gap: "0.5rem" }}>
            <label>
              Lookback hours
              <input
                type="number"
                min={1}
                value={refreshHours}
                onChange={(event) => setRefreshHours(event.target.value)}
                style={{ marginLeft: "0.5rem", width: "6rem" }}
              />
            </label>
            <button type="submit" className="button" disabled={isRefreshing}>
              {isRefreshing ? "Refreshing…" : "Refresh digest"}
            </button>
          </form>
        </header>
        {isDigestLoading ? <p>Loading digest…</p> : null}
        {digestError ? (
          <p role="alert" className="error">
            {digestError}
          </p>
        ) : null}
        {digest ? (
          <div className="stack" style={{ marginTop: "1rem", gap: "0.75rem" }}>
            <p>
              Generated {formatDate(digest.generated_at)} for window starting {" "}
              {formatDate(digest.window_start)}.
            </p>
            <table className="table" aria-label="Digest topic clusters">
              <thead>
                <tr>
                  <th scope="col">Topic</th>
                  <th scope="col">Summary</th>
                  <th scope="col">New docs</th>
                  <th scope="col">Total docs</th>
                </tr>
              </thead>
              <tbody>
                {digestTopics.length ? (
                  digestTopics.map((topic) => (
                    <tr key={topic.topic}>
                      <th scope="row">{topic.topic}</th>
                      <td>{topic.summary || "—"}</td>
                      <td>{topic.new_documents}</td>
                      <td>{topic.total_documents}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4}>No clusters were generated for this window.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="watchlist-admin" className="stack" style={{ gap: "1rem" }}>
        <header className="cluster" style={{ justifyContent: "space-between", gap: "1rem" }}>
          <div>
            <h2 id="watchlist-admin">Watchlists</h2>
            <p>Monitor topics, keywords, and authors for specific users.</p>
          </div>
          <div className="cluster" style={{ gap: "0.5rem" }}>
            <label>
              User ID
              <input
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                placeholder="owner-123"
                style={{ marginLeft: "0.5rem" }}
              />
            </label>
            <button
              type="button"
              className="button secondary"
              onClick={() => void loadWatchlists(userId.trim())}
              disabled={isWatchlistLoading}
            >
              {isWatchlistLoading ? "Loading…" : "Load watchlists"}
            </button>
          </div>
        </header>
        {watchlistsLoadedFor ? (
          <p>
            Loaded {watchlists.length} watchlists for <strong>{watchlistsLoadedFor}</strong>.
          </p>
        ) : null}
        {watchlistError ? (
          <p role="alert" className="error">
            {watchlistError}
          </p>
        ) : null}

        <form
          className="card stack"
          onSubmit={handleCreateWatchlist}
          style={{ padding: "1rem", gap: "0.75rem" }}
        >
          <h3>Create watchlist</h3>
          <div className="cluster" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
            <label>
              Name
              <input
                value={creationName}
                onChange={(event) => setCreationName(event.target.value)}
                required
                style={{ marginLeft: "0.5rem" }}
              />
            </label>
            <label>
              Cadence
              <select
                value={creationCadence}
                onChange={(event) => setCreationCadence(event.target.value)}
                style={{ marginLeft: "0.5rem" }}
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </label>
            <label>
              Delivery
              <input
                value={creationDeliveryChannels}
                onChange={(event) => setCreationDeliveryChannels(event.target.value)}
                style={{ marginLeft: "0.5rem" }}
                placeholder="in_app,email"
              />
            </label>
          </div>
          <div className="cluster" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
            <label>
              Topics
              <input
                value={creationTopics}
                onChange={(event) => setCreationTopics(event.target.value)}
                placeholder="Christology, Eschatology"
                style={{ marginLeft: "0.5rem" }}
              />
            </label>
            <label>
              Keywords
              <input
                value={creationKeywords}
                onChange={(event) => setCreationKeywords(event.target.value)}
                placeholder="resurrection, hope"
                style={{ marginLeft: "0.5rem" }}
              />
            </label>
            <label>
              Authors
              <input
                value={creationAuthors}
                onChange={(event) => setCreationAuthors(event.target.value)}
                placeholder="N. T. Wright"
                style={{ marginLeft: "0.5rem" }}
              />
            </label>
          </div>
          {creationError ? (
            <p role="alert" className="error">
              {creationError}
            </p>
          ) : null}
          <button type="submit" className="button" disabled={isCreating}>
            {isCreating ? "Creating…" : "Create"}
          </button>
        </form>

        <div className="cluster" style={{ alignItems: "center", gap: "0.5rem" }}>
          <label>
            <input
              type="checkbox"
              checked={showActiveOnly}
              onChange={(event) => {
                setShowActiveOnly(event.target.checked);
                setWatchlistPage(0);
              }}
            />
            Show active only
          </label>
        </div>

        <table className="table" aria-label="Watchlists">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Cadence</th>
              <th scope="col">Delivery</th>
              <th scope="col">Filters</th>
              <th scope="col">Status</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {paginatedWatchlists.length ? (
              paginatedWatchlists.map((watchlist) => (
                <tr key={watchlist.id}>
                  <th scope="row">
                    <input
                      aria-label={`Name for ${watchlist.name}`}
                      value={watchlist.name}
                      onChange={(event) => {
                        const value = event.target.value;
                        setWatchlists((current) =>
                          current.map((item) =>
                            item.id === watchlist.id ? { ...item, name: value } : item,
                          ),
                        );
                      }}
                    />
                    <div className="meta">Last run: {formatDate(watchlist.last_run)}</div>
                  </th>
                  <td>
                    <select
                      aria-label={`Cadence for ${watchlist.name}`}
                      value={watchlist.cadence}
                      onChange={(event) => {
                        const value = event.target.value;
                        setWatchlists((current) =>
                          current.map((item) =>
                            item.id === watchlist.id ? { ...item, cadence: value } : item,
                          ),
                        );
                      }}
                    >
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="monthly">Monthly</option>
                    </select>
                  </td>
                  <td>
                    <input
                      aria-label={`Delivery channels for ${watchlist.name}`}
                      value={commaList(watchlist.delivery_channels)}
                      onChange={(event) => {
                        const value = event.target.value;
                        const channels = value
                          .split(",")
                          .map((item) => item.trim())
                          .filter(Boolean);
                        setWatchlists((current) =>
                          current.map((item) =>
                            item.id === watchlist.id
                              ? { ...item, delivery_channels: channels }
                              : item,
                          ),
                        );
                      }}
                    />
                  </td>
                  <td>
                    <div className="stack" style={{ gap: "0.25rem" }}>
                      <label>
                        Topics
                        <input
                          value={commaList(watchlist.filters?.topics ?? null)}
                          onChange={(event) => {
                            const topics = parseCommaList(event.target.value) ?? [];
                            setWatchlists((current) =>
                              current.map((item) =>
                                item.id === watchlist.id
                                  ? {
                                      ...item,
                                      filters: { ...item.filters, topics },
                                    }
                                  : item,
                              ),
                            );
                          }}
                        />
                      </label>
                      <label>
                        Keywords
                        <input
                          value={commaList(watchlist.filters?.keywords ?? null)}
                          onChange={(event) => {
                            const keywords = parseCommaList(event.target.value) ?? [];
                            setWatchlists((current) =>
                              current.map((item) =>
                                item.id === watchlist.id
                                  ? {
                                      ...item,
                                      filters: { ...item.filters, keywords },
                                    }
                                  : item,
                              ),
                            );
                          }}
                        />
                      </label>
                      <label>
                        Authors
                        <input
                          value={commaList(watchlist.filters?.authors ?? null)}
                          onChange={(event) => {
                            const authors = parseCommaList(event.target.value) ?? [];
                            setWatchlists((current) =>
                              current.map((item) =>
                                item.id === watchlist.id
                                  ? {
                                      ...item,
                                      filters: { ...item.filters, authors },
                                    }
                                  : item,
                              ),
                            );
                          }}
                        />
                      </label>
                    </div>
                  </td>
                  <td>
                    <label>
                      <input
                        type="checkbox"
                        checked={watchlist.is_active}
                        onChange={(event) => {
                          const checked = event.target.checked;
                          setWatchlists((current) =>
                            current.map((item) =>
                              item.id === watchlist.id
                                ? { ...item, is_active: checked }
                                : item,
                            ),
                          );
                        }}
                      />
                      Active
                    </label>
                  </td>
                  <td>
                    <div className="stack" style={{ gap: "0.25rem" }}>
                      <button
                        type="button"
                        className="button secondary"
                        onClick={() => void updateWatchlist(watchlist)}
                      >
                        Save changes
                      </button>
                      <button
                        type="button"
                        className="button secondary"
                        onClick={() => void runWatchlist(watchlist.id, "preview")}
                      >
                        Preview
                      </button>
                      <button
                        type="button"
                        className="button"
                        onClick={() => void runWatchlist(watchlist.id, "run")}
                      >
                        Run now
                      </button>
                      <button
                        type="button"
                        className="button danger"
                        onClick={() => void deleteWatchlist(watchlist.id)}
                      >
                        Delete
                      </button>
                      <button
                        type="button"
                        className="button secondary"
                        onClick={() => void loadEvents(watchlist.id, eventsSince)}
                      >
                        View events
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6}>
                  {watchlistsLoadedFor
                    ? "No watchlists were found for this user."
                    : "Enter a user ID to load watchlists."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {filteredWatchlists.length > PAGE_SIZE ? (
          <div className="cluster" style={{ gap: "0.5rem" }}>
            <button
              type="button"
              className="button secondary"
              onClick={() => setWatchlistPage((page) => Math.max(page - 1, 0))}
              disabled={activePage === 0}
            >
              Previous
            </button>
            <span>
              Page {activePage + 1} of {totalPages}
            </span>
            <button
              type="button"
              className="button secondary"
              onClick={() =>
                setWatchlistPage((page) =>
                  page + 1 >= totalPages ? page : Math.min(page + 1, totalPages - 1),
                )
              }
              disabled={activePage + 1 >= totalPages}
            >
              Next
            </button>
          </div>
        ) : null}

        <div className="card stack" style={{ padding: "1rem", gap: "0.75rem" }}>
          <h3>Recent watchlist runs</h3>
          <label>
            Since timestamp (ISO)
            <input
              value={eventsSince}
              onChange={(event) => setEventsSince(event.target.value)}
              placeholder="2024-01-01T00:00:00Z"
              style={{ marginLeft: "0.5rem" }}
            />
          </label>
          {eventsLoading ? <p>Loading events…</p> : null}
          {eventsError ? (
            <p role="alert" className="error">
              {eventsError}
            </p>
          ) : null}
          {eventsWatchlistId ? (
            <p>
              Showing {events.length} events for watchlist <strong>{eventsWatchlistId}</strong>.
            </p>
          ) : null}
          <ul className="stack" style={{ gap: "0.5rem" }}>
            {events.map((event) => (
              <li key={`${event.watchlist_id}-${event.run_started}`} className="card" style={{ padding: "0.75rem" }}>
                <div className="cluster" style={{ justifyContent: "space-between" }}>
                  <strong>{formatDate(event.run_started)}</strong>
                  <span>{event.delivery_status ?? "pending"}</span>
                </div>
                {event.error ? <p role="alert">{event.error}</p> : null}
                <p>
                  {event.matches.length} matches · {event.document_ids.length} documents
                </p>
              </li>
            ))}
          </ul>
          {events.length === 0 && eventsWatchlistId ? <p>No events in this window.</p> : null}
        </div>

        <div className="card stack" style={{ padding: "1rem", gap: "0.75rem" }}>
          <h3>Most recent result</h3>
          {lastRunError ? (
            <p role="alert" className="error">
              {lastRunError}
            </p>
          ) : null}
          {lastRunResult ? (
            <div className="stack" style={{ gap: "0.5rem" }}>
              <p>
                {lastRunType === "preview" ? "Preview" : "Run"} completed at {" "}
                {formatDate(lastRunResult.run_completed)} with {lastRunResult.matches.length} matches.
              </p>
              {lastRunResult.error ? (
                <p role="alert">{lastRunResult.error}</p>
              ) : null}
              <details>
                <summary>View matches</summary>
                <ul className="stack" style={{ gap: "0.5rem", marginTop: "0.5rem" }}>
                  {lastRunResult.matches.map((match) => (
                    <li key={`${match.document_id}-${match.passage_id ?? "none"}`} className="card" style={{ padding: "0.5rem" }}>
                      <strong>{match.document_id}</strong>
                      {match.osis ? <div>OSIS: {match.osis}</div> : null}
                      {match.snippet ? <div>{match.snippet}</div> : null}
                      {match.reasons?.length ? (
                        <div>Reasons: {match.reasons.join(", ")}</div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          ) : (
            <p>No preview or run has been triggered yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
