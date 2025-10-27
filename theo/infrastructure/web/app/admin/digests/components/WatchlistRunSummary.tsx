import FormError from "../../../components/FormError";
import type { WatchlistRunResponse } from "../types";
import styles from "./WatchlistRunSummary.module.css";

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
    <div className={`card ${styles.container}`}>
      <h3>Most recent result</h3>
      <FormError message={error} />
      {result ? (
        <div className={styles.resultContent}>
          <p>
            {type === "preview" ? "Preview" : "Run"} completed at {formatDate(result.run_completed)} with {" "}
            {result.matches.length} matches.
          </p>
          <FormError message={result.error} />
          <details>
            <summary>View matches</summary>
            <ul className={styles.matchesList}>
              {result.matches.map((match) => (
                <li key={`${match.document_id}-${match.passage_id ?? "none"}`} className={`card ${styles.matchItem}`}>
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
