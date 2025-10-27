/** @jest-environment jsdom */

import { fireEvent, render, screen } from "@testing-library/react";

import DigestOverview from "../../../app/admin/digests/components/DigestOverview";
import WatchlistCreationForm from "../../../app/admin/digests/components/WatchlistCreationForm";
import WatchlistEventsPanel from "../../../app/admin/digests/components/WatchlistEventsPanel";
import WatchlistRunSummary from "../../../app/admin/digests/components/WatchlistRunSummary";
import WatchlistTable from "../../../app/admin/digests/components/WatchlistTable";
import type { TopicDigest, WatchlistResponse, WatchlistRunResponse } from "../../../app/admin/digests/types";

describe("admin digest components", () => {
  it("renders digest overview and triggers refresh", () => {
    const digest: TopicDigest = {
      generated_at: "2024-01-01T00:00:00Z",
      window_start: "2024-01-01T00:00:00Z",
      topics: [],
    };
    const onRefresh = jest.fn();
    render(
      <DigestOverview
        digest={digest}
        isLoading={false}
        error={null}
        refreshHours="24"
        onRefreshHoursChange={() => undefined}
        onRefresh={onRefresh}
        isRefreshing={false}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /refresh digest/i }));
    expect(onRefresh).toHaveBeenCalled();
  });

  it("renders watchlist creation form", () => {
    const onSubmit = jest.fn();
    render(
      <WatchlistCreationForm
        name=""
        cadence="daily"
        deliveryChannels="in_app"
        topics=""
        keywords=""
        authors=""
        osis=""
        onNameChange={() => undefined}
        onCadenceChange={() => undefined}
        onDeliveryChannelsChange={() => undefined}
        onTopicsChange={() => undefined}
        onKeywordsChange={() => undefined}
        onAuthorsChange={() => undefined}
        onOsisChange={() => undefined}
        onSubmit={onSubmit}
        isCreating={false}
        error={null}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "Watchlist" } });
    fireEvent.click(screen.getByRole("button", { name: /create watchlist/i }));
  });

  it("renders watchlist table and handles actions", () => {
    const watchlists: WatchlistResponse[] = [
      {
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
      },
    ];
    const onEdit = jest.fn();
    const onSave = jest.fn();
    const onPreview = jest.fn();
    const onRun = jest.fn();
    const onDelete = jest.fn();
    const onViewEvents = jest.fn();
    render(
      <WatchlistTable
        watchlists={watchlists}
        totalCount={1}
        page={0}
        totalPages={1}
        showActiveOnly={false}
        onToggleActiveOnly={() => undefined}
        onPreviousPage={() => undefined}
        onNextPage={() => undefined}
        loadedFor="user"
        onEdit={onEdit}
        onSave={onSave}
        onPreview={onPreview}
        onRun={onRun}
        onDelete={onDelete}
        onViewEvents={onViewEvents}
        formatDate={() => "—"}
        toCommaList={() => ""}
        fromCommaList={() => []}
      />,
    );
    fireEvent.change(screen.getByDisplayValue("Name"), { target: { value: "Updated" } });
    expect(onEdit).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
    expect(onSave).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /preview/i }));
    expect(onPreview).toHaveBeenCalled();
  });

  it("renders events panel", () => {
    const events: WatchlistRunResponse[] = [
      {
        id: "run",
        watchlist_id: "1",
        run_started: "2024-01-01T00:00:00Z",
        run_completed: "2024-01-01T00:00:00Z",
        window_start: "",
        matches: [],
        document_ids: [],
        passage_ids: [],
        delivery_status: null,
        error: null,
      },
    ];
    render(
      <WatchlistEventsPanel
        events={events}
        eventsSince=""
        onEventsSinceChange={() => undefined}
        eventsLoading={false}
        eventsError={null}
        eventsWatchlistId="1"
        formatDate={() => "date"}
      />,
    );
    expect(screen.getByText(/Showing 1 events/)).toBeInTheDocument();
  });

  it("renders run summary", () => {
    const result: WatchlistRunResponse = {
      id: "run",
      watchlist_id: "1",
      run_started: "2024-01-01T00:00:00Z",
      run_completed: "2024-01-01T00:00:00Z",
      window_start: "",
      matches: [],
      document_ids: [],
      passage_ids: [],
      delivery_status: null,
      error: null,
    };
    render(<WatchlistRunSummary result={result} type="run" error={null} formatDate={() => "date"} />);
    expect(screen.getByText(/Run completed/)).toBeInTheDocument();
  });
});
