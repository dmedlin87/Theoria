import type { WatchlistRunResponse } from "../types";

type WatchlistRunSummaryProps = {
  result: WatchlistRunResponse | null;
  type: "preview" | "run" | null;
  error: string | null;
  formatDate: (value: string | null) => string;
};

export default function WatchlistRunSummary({
  result,
  type,
  error,
  formatDate,
}: WatchlistRunSummaryProps): JSX.Element {
  return (
    <div className="card stack" style={{ padding: "1rem", gap: "0.75rem" }}>
      <h3>Most recent result</h3>
      {error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : null}
      {result ? (
        <div className="stack" style={{ gap: "0.5rem" }}>
          <p>
            {type === "preview" ? "Preview" : "Run"} completed at {formatDate(result.run_completed)} with {" "}
            {result.matches.length} matches.
          </p>
          {result.error ? <p role="alert">{result.error}</p> : null}
          <details>
            <summary>View matches</summary>
            <ul className="stack" style={{ gap: "0.5rem", marginTop: "0.5rem" }}>
              {result.matches.map((match) => (
                <li key={`${match.document_id}-${match.passage_id ?? "none"}`} className="card" style={{ padding: "0.5rem" }}>
                  <strong>{match.document_id}</strong>
                  {match.osis ? <div>OSIS: {match.osis}</div> : null}
                  {match.snippet ? <div>{match.snippet}</div> : null}
                  {match.reasons?.length ? <div>Reasons: {match.reasons.join(", ")}</div> : null}
                </li>
              ))}
            </ul>
          </details>
        </div>
      ) : (
        <p>No preview or run has been triggered yet.</p>
      )}
    </div>
  );
}
