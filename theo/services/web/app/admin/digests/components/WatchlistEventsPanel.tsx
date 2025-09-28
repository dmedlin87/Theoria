import type { WatchlistRunResponse } from "../types";

type WatchlistEventsPanelProps = {
  events: WatchlistRunResponse[];
  eventsSince: string;
  onEventsSinceChange: (value: string) => void;
  eventsLoading: boolean;
  eventsError: string | null;
  eventsWatchlistId: string | null;
  formatDate: (value: string | null) => string;
};

export default function WatchlistEventsPanel({
  events,
  eventsSince,
  onEventsSinceChange,
  eventsLoading,
  eventsError,
  eventsWatchlistId,
  formatDate,
}: WatchlistEventsPanelProps): JSX.Element {
  return (
    <div className="card stack" style={{ padding: "1rem", gap: "0.75rem" }}>
      <h3>Recent watchlist runs</h3>
      <label>
        Since timestamp (ISO)
        <input
          value={eventsSince}
          onChange={(event) => onEventsSinceChange(event.target.value)}
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
  );
}
