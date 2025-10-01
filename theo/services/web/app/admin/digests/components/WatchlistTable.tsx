import type { WatchlistResponse } from "../types";

type WatchlistTableProps = {
  watchlists: WatchlistResponse[];
  totalCount: number;
  page: number;
  totalPages: number;
  showActiveOnly: boolean;
  onToggleActiveOnly: (value: boolean) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
  loadedFor: string | null;
  onEdit: (id: string, updates: Partial<WatchlistResponse>) => void;
  onSave: (watchlist: WatchlistResponse) => void;
  onPreview: (id: string) => void;
  onRun: (id: string) => void;
  onDelete: (id: string) => void;
  onViewEvents: (id: string) => void;
  formatDate: (value: string | null) => string;
  toCommaList: (values: string[] | null | undefined) => string;
  fromCommaList: (value: string) => string[];
};

export default function WatchlistTable({
  watchlists,
  totalCount,
  page,
  totalPages,
  showActiveOnly,
  onToggleActiveOnly,
  onPreviousPage,
  onNextPage,
  loadedFor,
  onEdit,
  onSave,
  onPreview,
  onRun,
  onDelete,
  onViewEvents,
  formatDate,
  toCommaList,
  fromCommaList,
}: WatchlistTableProps): JSX.Element {
  return (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="cluster" style={{ justifyContent: "space-between", gap: "0.5rem" }}>
        <div>
          <h2 id="watchlist-admin">Watchlists</h2>
          <p>Monitor topics, keywords, and authors for specific users.</p>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input
            type="checkbox"
            checked={showActiveOnly}
            onChange={(event) => onToggleActiveOnly(event.target.checked)}
          />
          Show active only
        </label>
      </div>
      <table className="table" aria-labelledby="watchlist-admin">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Cadence</th>
            <th scope="col">Delivery</th>
            <th scope="col">Filters</th>
            <th scope="col">Active</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {watchlists.length ? (
            watchlists.map((watchlist) => (
              <tr key={watchlist.id}>
                <th scope="row">
                  <input
                    value={watchlist.name}
                    onChange={(event) => onEdit(watchlist.id, { name: event.target.value })}
                  />
                  <div className="meta">Last run: {formatDate(watchlist.last_run)}</div>
                </th>
                <td>
                  <select
                    aria-label={`Cadence for ${watchlist.name}`}
                    value={watchlist.cadence}
                    onChange={(event) => onEdit(watchlist.id, { cadence: event.target.value })}
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`Delivery channels for ${watchlist.name}`}
                    value={toCommaList(watchlist.delivery_channels)}
                    onChange={(event) =>
                      onEdit(watchlist.id, { delivery_channels: fromCommaList(event.target.value) })
                    }
                  />
                </td>
                <td>
                  <div className="stack" style={{ gap: "0.25rem" }}>
                    <label>
                      Topics
                      <input
                        value={toCommaList(watchlist.filters?.topics)}
                        onChange={(event) =>
                          onEdit(watchlist.id, {
                            filters: { ...watchlist.filters, topics: fromCommaList(event.target.value) },
                          })
                        }
                      />
                    </label>
                    <label>
                      Keywords
                      <input
                        value={toCommaList(watchlist.filters?.keywords)}
                        onChange={(event) =>
                          onEdit(watchlist.id, {
                            filters: { ...watchlist.filters, keywords: fromCommaList(event.target.value) },
                          })
                        }
                      />
                    </label>
                    <label>
                      Authors
                      <input
                        value={toCommaList(watchlist.filters?.authors)}
                        onChange={(event) =>
                          onEdit(watchlist.id, {
                            filters: { ...watchlist.filters, authors: fromCommaList(event.target.value) },
                          })
                        }
                      />
                    </label>
                    <label>
                      OSIS references
                      <input
                        value={toCommaList(watchlist.filters?.osis)}
                        onChange={(event) =>
                          onEdit(watchlist.id, {
                            filters: { ...watchlist.filters, osis: fromCommaList(event.target.value) },
                          })
                        }
                      />
                    </label>
                  </div>
                </td>
                <td>
                  <label>
                    <input
                      type="checkbox"
                      checked={watchlist.is_active}
                      onChange={(event) => onEdit(watchlist.id, { is_active: event.target.checked })}
                    />
                    Active
                  </label>
                </td>
                <td>
                  <div className="stack" style={{ gap: "0.25rem" }}>
                    <button type="button" className="button secondary" onClick={() => onSave(watchlist)}>
                      Save changes
                    </button>
                    <button type="button" className="button secondary" onClick={() => onPreview(watchlist.id)}>
                      Preview
                    </button>
                    <button type="button" className="button" onClick={() => onRun(watchlist.id)}>
                      Run now
                    </button>
                    <button type="button" className="button danger" onClick={() => onDelete(watchlist.id)}>
                      Delete
                    </button>
                    <button type="button" className="button secondary" onClick={() => onViewEvents(watchlist.id)}>
                      View events
                    </button>
                  </div>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={6}>
                {loadedFor ? "No watchlists were found for this user." : "Enter a user ID to load watchlists."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {totalCount > watchlists.length ? (
        <div className="cluster" style={{ gap: "0.5rem" }}>
          <button type="button" className="button secondary" onClick={onPreviousPage} disabled={page === 0}>
            Previous
          </button>
          <span>
            Page {page + 1} of {totalPages}
          </span>
          <button
            type="button"
            className="button secondary"
            onClick={onNextPage}
            disabled={page + 1 >= totalPages}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}
