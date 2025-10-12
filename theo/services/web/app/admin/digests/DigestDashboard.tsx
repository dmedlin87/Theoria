"use client";

import { useEffect, useMemo, useState } from "react";

import FormError from "../../components/FormError";
import { createTheoApiClient } from "../../lib/api-client";
import DigestOverview from "./components/DigestOverview";
import WatchlistCreationForm from "./components/WatchlistCreationForm";
import WatchlistEventsPanel from "./components/WatchlistEventsPanel";
import WatchlistRunSummary from "./components/WatchlistRunSummary";
import WatchlistTable from "./components/WatchlistTable";
import {
  useCommaListHelpers,
  useTopicDigest,
  useWatchlistCrud,
  useWatchlistEvents,
  useWatchlistPagination,
} from "./hooks";
import type { WatchlistResponse, WatchlistRunResponse } from "./types";

const PAGE_SIZE = 5;

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function DigestDashboard(): JSX.Element {
  const apiClient = useMemo(() => createTheoApiClient(), []);
  const topicDigest = useTopicDigest(apiClient);
  const watchlistCrud = useWatchlistCrud(apiClient);
  const pagination = useWatchlistPagination(watchlistCrud.watchlists, PAGE_SIZE);
  const watchlistEvents = useWatchlistEvents(apiClient);
  const { toCommaList, fromCommaList } = useCommaListHelpers();

  const [refreshHours, setRefreshHours] = useState("168");
  const [userId, setUserId] = useState("");

  const [creationName, setCreationName] = useState("");
  const [creationCadence, setCreationCadence] = useState("daily");
  const [creationDeliveryChannels, setCreationDeliveryChannels] = useState("in_app");
  const [creationTopics, setCreationTopics] = useState("");
  const [creationKeywords, setCreationKeywords] = useState("");
  const [creationAuthors, setCreationAuthors] = useState("");
  const [creationOsis, setCreationOsis] = useState("");
  const [creationError, setCreationError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const [eventsSince, setEventsSince] = useState("");
  const [lastRunResult, setLastRunResult] = useState<WatchlistRunResponse | null>(null);
  const [lastRunType, setLastRunType] = useState<"preview" | "run" | null>(null);
  const [lastRunError, setLastRunError] = useState<string | null>(null);

  useEffect(() => {
    void topicDigest.loadDigest();
  }, [topicDigest.loadDigest]);

  const handleRefreshDigest = async () => {
    const hours = Number.parseInt(refreshHours, 10);
    if (!Number.isFinite(hours) || hours <= 0) {
      topicDigest.setError("Hours must be a positive number");
      return;
    }
    await topicDigest.refreshDigest(hours);
  };

  const handleCreateWatchlist = async () => {
    if (!userId.trim()) {
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
      const deliveryChannels = fromCommaList(creationDeliveryChannels);
      const toOptional = (value: string): string[] | null => {
        const items = fromCommaList(value);
        return items.length ? items : null;
      };
      await watchlistCrud.createWatchlist({
        user_id: userId.trim(),
        name: creationName.trim(),
        cadence: creationCadence,
        delivery_channels: deliveryChannels,
        filters: {
          topics: toOptional(creationTopics),
          keywords: toOptional(creationKeywords),
          authors: toOptional(creationAuthors),
          osis: toOptional(creationOsis),
        },
      });
      setCreationName("");
      setCreationTopics("");
      setCreationKeywords("");
      setCreationAuthors("");
      setCreationOsis("");
    } catch (error) {
      setCreationError((error as Error).message);
    } finally {
      setIsCreating(false);
    }
  };

  const handleSaveWatchlist = async (watchlist: WatchlistResponse) => {
    try {
      await watchlistCrud.saveWatchlist(watchlist);
    } catch (error) {
      watchlistCrud.setError((error as Error).message);
    }
  };

  const handlePreviewWatchlist = async (watchlistId: string) => {
    try {
      const result = await watchlistCrud.runWatchlist(watchlistId, "preview");
      setLastRunType("preview");
      setLastRunResult(result);
      setLastRunError(null);
    } catch (error) {
      setLastRunError((error as Error).message);
    }
  };

  const handleRunWatchlist = async (watchlistId: string) => {
    try {
      const result = await watchlistCrud.runWatchlist(watchlistId, "run");
      setLastRunType("run");
      setLastRunResult(result);
      setLastRunError(null);
    } catch (error) {
      setLastRunError((error as Error).message);
    }
  };

  const handleDeleteWatchlist = async (watchlistId: string) => {
    try {
      await watchlistCrud.deleteWatchlist(watchlistId);
    } catch (error) {
      watchlistCrud.setError((error as Error).message);
    }
  };

  const handleViewEvents = async (watchlistId: string) => {
    await watchlistEvents.loadEvents(watchlistId, eventsSince);
  };

  const paginatedWatchlists = pagination.paginated;

  return (
    <div className="stack" style={{ gap: "2rem" }}>
      <DigestOverview
        digest={topicDigest.digest}
        isLoading={topicDigest.isLoading}
        error={topicDigest.error}
        refreshHours={refreshHours}
        onRefreshHoursChange={setRefreshHours}
        onRefresh={handleRefreshDigest}
        isRefreshing={topicDigest.isRefreshing}
      />

      <section aria-labelledby="watchlist-admin" className="stack" style={{ gap: "1rem" }}>
        <div className="cluster" style={{ justifyContent: "space-between", gap: "1rem" }}>
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
              onClick={() => void watchlistCrud.loadWatchlists(userId.trim())}
              disabled={watchlistCrud.isLoading}
            >
              {watchlistCrud.isLoading ? "Loading…" : "Load watchlists"}
            </button>
          </div>
          <WatchlistCreationForm
            name={creationName}
            cadence={creationCadence}
            deliveryChannels={creationDeliveryChannels}
            topics={creationTopics}
            keywords={creationKeywords}
            authors={creationAuthors}
            osis={creationOsis}
            onNameChange={setCreationName}
            onCadenceChange={setCreationCadence}
            onDeliveryChannelsChange={setCreationDeliveryChannels}
            onTopicsChange={setCreationTopics}
            onKeywordsChange={setCreationKeywords}
            onAuthorsChange={setCreationAuthors}
            onOsisChange={setCreationOsis}
            onSubmit={handleCreateWatchlist}
            isCreating={isCreating}
            error={creationError}
          />
        </div>

        {watchlistCrud.loadedFor ? (
          <p>
            Loaded {watchlistCrud.watchlists.length} watchlists for <strong>{watchlistCrud.loadedFor}</strong>.
          </p>
        ) : null}
        <FormError message={watchlistCrud.error} />

        <WatchlistTable
          watchlists={paginatedWatchlists}
          totalCount={pagination.totalCount}
          page={pagination.page}
          totalPages={pagination.totalPages}
          showActiveOnly={pagination.showActiveOnly}
          onToggleActiveOnly={pagination.setShowActiveOnly}
          onPreviousPage={() => pagination.setPage(Math.max(pagination.page - 1, 0))}
          onNextPage={() => pagination.setPage(Math.min(pagination.page + 1, pagination.totalPages - 1))}
          loadedFor={watchlistCrud.loadedFor}
          onEdit={watchlistCrud.editWatchlist}
          onSave={(watchlist) => void handleSaveWatchlist(watchlist)}
          onPreview={handlePreviewWatchlist}
          onRun={handleRunWatchlist}
          onDelete={handleDeleteWatchlist}
          onViewEvents={handleViewEvents}
          formatDate={formatDate}
          toCommaList={toCommaList}
          fromCommaList={fromCommaList}
        />

        <WatchlistEventsPanel
          events={watchlistEvents.events}
          eventsSince={eventsSince}
          onEventsSinceChange={setEventsSince}
          eventsLoading={watchlistEvents.eventsLoading}
          eventsError={watchlistEvents.eventsError}
          eventsWatchlistId={watchlistEvents.eventsWatchlistId}
          formatDate={formatDate}
        />

        <WatchlistRunSummary
          result={lastRunResult}
          type={lastRunType}
          error={lastRunError}
          formatDate={formatDate}
        />
      </section>
    </div>
  );
}
