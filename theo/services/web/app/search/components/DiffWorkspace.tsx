"use client";

import type { DiffSummary } from "./SearchPageClient";

type DiffWorkspaceProps = {
  diffSelection: string[];
  diffSummary: DiffSummary | null;
  onClear: () => void;
};

export function DiffWorkspace({ diffSelection, diffSummary, onClear }: DiffWorkspaceProps): JSX.Element {
  return (
    <aside className="diff-panel">
      <div className="diff-panel__header">
        <h3 className="diff-panel__title">Diff workspace</h3>
        <button type="button" onClick={onClear}>
          Clear selection
        </button>
      </div>
      {diffSummary ? (
        <div className="diff-panel__body">
          <p className="diff-panel__summary">
            Comparing <strong>{diffSummary.first.title}</strong> and <strong>{diffSummary.second.title}</strong>
          </p>
          <ul className="diff-panel__stats">
            <li>
              {diffSummary.first.passages.length} passages in first group ({diffSummary.uniqueToFirst.length} unique)
            </li>
            <li>
              {diffSummary.second.passages.length} passages in second group ({diffSummary.uniqueToSecond.length} unique)
            </li>
            <li>{diffSummary.shared} overlapping passages across both groups</li>
          </ul>
          {(diffSummary.uniqueToFirst.length > 0 || diffSummary.uniqueToSecond.length > 0) && (
            <div className="diff-panel__unique">
              {diffSummary.uniqueToFirst.length > 0 && (
                <p className="diff-panel__text">
                  Unique to {diffSummary.first.title}: {diffSummary.uniqueToFirst.join(", ")}
                </p>
              )}
              {diffSummary.uniqueToSecond.length > 0 && (
                <p className="diff-panel__text">
                  Unique to {diffSummary.second.title}: {diffSummary.uniqueToSecond.join(", ")}
                </p>
              )}
            </div>
          )}
        </div>
      ) : (
        <p className="diff-panel__empty">
          {diffSelection.length < 2
            ? "Select another group to compare. Up to two result groups can be diffed at once."
            : "Select another group to compare. Up to two result groups can be diffed at once."}
        </p>
      )}
    </aside>
  );
}
