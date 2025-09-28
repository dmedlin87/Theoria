/** @jest-environment jsdom */

import { act, renderHook } from "@testing-library/react";

import type { TheoApiClient } from "../../../app/lib/api-client";
import {
  useCommaListHelpers,
  useTopicDigest,
  useWatchlistCrud,
  useWatchlistEvents,
  useWatchlistPagination,
} from "../../../app/admin/digests/hooks";
import type {
  TopicDigest,
  WatchlistResponse,
  WatchlistRunResponse,
} from "../../../app/admin/digests/types";

type MockApi = Pick<
  TheoApiClient,
  | "getDigest"
  | "refreshDigest"
  | "listWatchlists"
  | "createWatchlist"
  | "updateWatchlist"
  | "deleteWatchlist"
  | "runWatchlist"
  | "fetchWatchlistEvents"
>;

function createMockApi(): jest.Mocked<MockApi> {
  return {
    getDigest: jest.fn(),
    refreshDigest: jest.fn(),
    listWatchlists: jest.fn(),
    createWatchlist: jest.fn(),
    updateWatchlist: jest.fn(),
    deleteWatchlist: jest.fn(),
    runWatchlist: jest.fn(),
    fetchWatchlistEvents: jest.fn(),
  };
}

describe("admin digest hooks", () => {
  it("loads and refreshes digest", async () => {
    const api = createMockApi();
    const digest: TopicDigest = {
      generated_at: "2024-01-01T00:00:00Z",
      window_start: "2024-01-01T00:00:00Z",
      topics: [],
    };
    api.getDigest.mockResolvedValueOnce(digest);
    const { result } = renderHook(() => useTopicDigest(api as unknown as TheoApiClient));
    await act(async () => {
      await result.current.loadDigest();
    });
    expect(result.current.digest).toEqual(digest);
    api.refreshDigest.mockResolvedValueOnce(digest);
    api.getDigest.mockResolvedValueOnce(digest);
    await act(async () => {
      await result.current.refreshDigest(24);
    });
    expect(api.refreshDigest).toHaveBeenCalledWith(24);
  });

  it("manages watchlist CRUD operations", async () => {
    const api = createMockApi();
    const watchlist: WatchlistResponse = {
      id: "1",
      user_id: "user",
      name: "Name",
      filters: { topics: [], authors: [], keywords: [] },
      cadence: "daily",
      delivery_channels: ["in_app"],
      is_active: true,
      last_run: null,
      created_at: "",
      updated_at: "",
    };
    api.listWatchlists.mockResolvedValueOnce([watchlist]);
    const { result } = renderHook(() => useWatchlistCrud(api as unknown as TheoApiClient));
    await act(async () => {
      await result.current.loadWatchlists("user");
    });
    expect(result.current.watchlists).toHaveLength(1);

    const updated = { ...watchlist, name: "Updated" };
    api.updateWatchlist.mockResolvedValueOnce(updated);
    await act(async () => {
      await result.current.saveWatchlist(updated);
    });
    expect(api.updateWatchlist).toHaveBeenCalledWith("1", { name: "Updated" });

    api.deleteWatchlist.mockResolvedValueOnce();
    await act(async () => {
      await result.current.deleteWatchlist("1");
    });
    expect(result.current.watchlists).toHaveLength(0);
  });

  it("paginates watchlists", () => {
    const watchlists = Array.from({ length: 7 }, (_, index) => ({
      id: `${index}`,
      user_id: "user",
      name: "Name",
      filters: {},
      cadence: "daily",
      delivery_channels: [],
      is_active: true,
      last_run: null,
      created_at: "",
      updated_at: "",
    })) as WatchlistResponse[];
    const { result } = renderHook(() => useWatchlistPagination(watchlists, 5));
    expect(result.current.totalPages).toBe(2);
    expect(result.current.paginated).toHaveLength(5);
  });

  it("loads watchlist events", async () => {
    const api = createMockApi();
    const events: WatchlistRunResponse[] = [
      {
        id: "run",
        watchlist_id: "1",
        run_started: "",
        run_completed: "",
        window_start: "",
        matches: [],
        document_ids: [],
        passage_ids: [],
        delivery_status: null,
        error: null,
      },
    ];
    api.fetchWatchlistEvents.mockResolvedValueOnce(events);
    const { result } = renderHook(() => useWatchlistEvents(api as unknown as TheoApiClient));
    await act(async () => {
      await result.current.loadEvents("1", "");
    });
    expect(result.current.events).toEqual(events);
  });

  it("provides comma list helpers", () => {
    const helpers = useCommaListHelpers();
    expect(helpers.toCommaList(["a", "b"])).toBe("a, b");
    expect(helpers.fromCommaList("a, b")).toEqual(["a", "b"]);
  });
});
