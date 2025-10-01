import type { TopicDigest } from "../types";

type DigestOverviewProps = {
  digest: TopicDigest | null;
  isLoading: boolean;
  error: string | null;
  refreshHours: string;
  onRefreshHoursChange: (value: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
};

export default function DigestOverview({
  digest,
  isLoading,
  error,
  refreshHours,
  onRefreshHoursChange,
  onRefresh,
  isRefreshing,
}: DigestOverviewProps): JSX.Element {
  const topics = digest?.topics ?? [];
  const formatTimestamp = (value: string): string => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  };
  return (
    <section aria-labelledby="digest-overview">
      <header className="cluster" style={{ justifyContent: "space-between", gap: "1rem" }}>
        <div>
          <h1 id="digest-overview">Topic digests</h1>
          <p>View the latest topical activity across the corpus and trigger a new digest run.</p>
        </div>
        <form
          className="cluster"
          onSubmit={(event) => {
            event.preventDefault();
            onRefresh();
          }}
          style={{ gap: "0.5rem" }}
        >
          <label>
            Lookback hours
            <input
              type="number"
              min={1}
              value={refreshHours}
              onChange={(event) => onRefreshHoursChange(event.target.value)}
              style={{ marginLeft: "0.5rem", width: "6rem" }}
            />
          </label>
          <button type="submit" className="button" disabled={isRefreshing}>
            {isRefreshing ? "Refreshing…" : "Refresh digest"}
          </button>
        </form>
      </header>
      {isLoading ? <p>Loading digest…</p> : null}
      {error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : null}
      {digest ? (
        <div className="stack" style={{ marginTop: "1rem", gap: "0.75rem" }}>
          <p>
            Generated {formatTimestamp(digest.generated_at)} for window starting {" "}
            {formatTimestamp(digest.window_start)}.
          </p>
          <table className="table" aria-label="Digest topic clusters">
            <thead>
              <tr>
                <th scope="col">Topic</th>
                <th scope="col">New docs</th>
                <th scope="col">Total docs</th>
              </tr>
            </thead>
            <tbody>
              {topics.length ? (
                topics.map((topic) => (
                  <tr key={topic.topic}>
                    <th scope="row">{topic.topic}</th>
                    <td>{topic.new_documents}</td>
                    <td>{topic.total_documents}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3}>No clusters were generated for this window.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
