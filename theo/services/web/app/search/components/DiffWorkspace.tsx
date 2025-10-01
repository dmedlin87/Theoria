"use client";

import type { DiffSummary } from "./SearchPageClient";

type DiffWorkspaceProps = {
  diffSelection: string[];
  diffSummary: DiffSummary | null;
  onClear: () => void;
};

export function DiffWorkspace({ diffSelection, diffSummary, onClear }: DiffWorkspaceProps): JSX.Element {
  return (
    <aside
      style={{
        margin: "1.5rem 0",
        padding: "1rem",
        border: "1px solid #cbd5f5",
        borderRadius: "0.75rem",
        background: "#f4f7ff",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
        <h3 style={{ margin: 0 }}>Diff workspace</h3>
        <button type="button" onClick={onClear}>
          Clear selection
        </button>
      </div>
      {diffSummary ? (
        <div style={{ marginTop: "0.75rem" }}>
          <p style={{ margin: "0 0 0.5rem" }}>
            Comparing <strong>{diffSummary.first.title}</strong> and <strong>{diffSummary.second.title}</strong>
          </p>
          <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
            <li>
              {diffSummary.first.passages.length} passages in first group ({diffSummary.uniqueToFirst.length} unique)
            </li>
            <li>
              {diffSummary.second.passages.length} passages in second group ({diffSummary.uniqueToSecond.length} unique)
            </li>
            <li>{diffSummary.shared} overlapping passages across both groups</li>
          </ul>
          {(diffSummary.uniqueToFirst.length > 0 || diffSummary.uniqueToSecond.length > 0) && (
            <div style={{ marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}>
              {diffSummary.uniqueToFirst.length > 0 && (
                <p style={{ margin: 0 }}>
                  Unique to {diffSummary.first.title}: {diffSummary.uniqueToFirst.join(", ")}
                </p>
              )}
              {diffSummary.uniqueToSecond.length > 0 && (
                <p style={{ margin: 0 }}>
                  Unique to {diffSummary.second.title}: {diffSummary.uniqueToSecond.join(", ")}
                </p>
              )}
            </div>
          )}
        </div>
      ) : (
        <p style={{ marginTop: "0.75rem" }}>
          {diffSelection.length < 2
            ? "Select another group to compare. Up to two result groups can be diffed at once."
            : "Select another group to compare. Up to two result groups can be diffed at once."}
        </p>
      )}
    </aside>
  );
}
