"use client";

import Link from "next/link";

import type { Dispatch, SetStateAction } from "react";

import type { DocumentGroup, SearchResult } from "../types";

export type SearchResultsListProps = {
  groups: DocumentGroup[];
  activeActionsGroupId: string | null;
  onActiveChange: Dispatch<SetStateAction<string | null>>;
  onExportGroup: (group: DocumentGroup) => void;
  onToggleDiffGroup: (groupId: string) => void;
  diffSelection: string[];
  showAdvancedHints: boolean;
  formatAnchor: (passage: {
    page_no?: number | null;
    t_start?: number | null;
    t_end?: number | null;
  }) => string;
  buildPassageLink: (
    documentId: string,
    passageId: string,
    options: { pageNo?: number | null; tStart?: number | null },
  ) => string;
  highlightTokens: (text: string) => JSX.Element;
  onPassageClick: (result: SearchResult) => void;
};

export default function SearchResultsList({
  groups,
  activeActionsGroupId,
  onActiveChange,
  onExportGroup,
  onToggleDiffGroup,
  diffSelection,
  showAdvancedHints,
  formatAnchor,
  buildPassageLink,
  highlightTokens,
  onPassageClick,
}: SearchResultsListProps): JSX.Element {
  if (groups.length === 0) {
    return <div style={{ display: "grid", gap: "1rem" }} />;
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {groups.map((group) => {
        const isSelectedForDiff = diffSelection.includes(group.documentId);
        const diffLabel = isSelectedForDiff
          ? "Remove from diff"
          : diffSelection.length >= 2
            ? "Replace in diff"
            : "Add to diff";
        const showGroupActions = activeActionsGroupId === group.documentId;

        return (
          <article
            key={group.documentId}
            style={{
              background: "#fff",
              borderRadius: "0.75rem",
              padding: "1.25rem",
              border: isSelectedForDiff ? "2px solid #3b82f6" : "1px solid #e2e8f0",
            }}
            tabIndex={0}
            onFocus={() => onActiveChange(group.documentId)}
            onBlur={() =>
              onActiveChange((current) => (current === group.documentId ? null : current))
            }
            onMouseEnter={() => onActiveChange(group.documentId)}
            onMouseLeave={() =>
              onActiveChange((current) => (current === group.documentId ? null : current))
            }
          >
            <header
              style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem" }}
            >
              <div>
                <h3 style={{ margin: "0 0 0.25rem" }}>{group.title}</h3>
                {typeof group.rank === "number" && (
                  <p style={{ margin: 0 }}>
                    Document rank #{group.rank}
                    {showAdvancedHints && (
                      <span
                        style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "#64748b" }}
                        title="Lower rank numbers indicate higher retrieval relevance."
                      >
                        (lower is better)
                      </span>
                    )}
                  </p>
                )}
                {typeof group.score === "number" && (
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "#555" }}>
                    Document score {group.score.toFixed(2)}
                    {showAdvancedHints && (
                      <span
                        style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "#64748b" }}
                        title="Combined retriever confidence; higher scores indicate stronger matches."
                      >
                        (higher is better)
                      </span>
                    )}
                  </p>
                )}
              </div>
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                  opacity: showGroupActions ? 1 : 0,
                  visibility: showGroupActions ? "visible" : "hidden",
                  pointerEvents: showGroupActions ? "auto" : "none",
                  transition: "opacity 0.15s ease",
                }}
              >
                <button type="button" onClick={() => onExportGroup(group)}>
                  Export JSON
                </button>
                <button type="button" onClick={() => onToggleDiffGroup(group.documentId)}>
                  {diffLabel}
                </button>
              </div>
            </header>
            <ul
              style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "0.75rem" }}
            >
              {group.passages.map((result) => {
                const anchorDescription = formatAnchor({
                  page_no: result.page_no ?? null,
                  t_start: result.t_start ?? null,
                  t_end: result.t_end ?? null,
                });
                return (
                  <li key={result.id} style={{ border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "0.75rem" }}>
                    <div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          gap: "1rem",
                        }}
                      >
                        <p style={{ margin: 0, flex: 1 }}>{result.snippet}</p>
                        <Link
                          href={buildPassageLink(result.document_id, result.id, {
                            pageNo: result.page_no ?? null,
                            tStart: result.t_start ?? null,
                          })}
                          onClick={() => onPassageClick(result)}
                          style={{ whiteSpace: "nowrap", fontWeight: 500 }}
                        >
                          Open passage
                        </Link>
                      </div>
                      {(anchorDescription || result.osis_ref) && (
                        <div style={{ marginTop: "0.5rem" }}>
                          {anchorDescription && <p style={{ margin: "0 0 0.25rem" }}>{anchorDescription}</p>}
                          {result.osis_ref && <p style={{ margin: 0 }}>OSIS: {result.osis_ref}</p>}
                        </div>
                      )}
                      {Array.isArray(result.highlights) && result.highlights.length > 0 && (
                        <div style={{ marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}>
                          {result.highlights.map((highlight) => (
                            <p
                              key={highlight}
                              style={{
                                margin: 0,
                                fontSize: "0.9rem",
                                background: "#f6f8fb",
                                padding: "0.5rem",
                                borderRadius: "0.5rem",
                              }}
                            >
                              {highlightTokens(highlight)}
                            </p>
                          ))}
                        </div>
                      )}
                      {typeof result.score === "number" && (
                        <p style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "#555" }}>
                          Passage score {result.score.toFixed(2)}
                          {showAdvancedHints && (
                            <span
                              style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "#64748b" }}
                              title="Reranker confidence for this passage; higher scores indicate stronger matches."
                            >
                              (higher is better)
                            </span>
                          )}
                        </p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </article>
        );
      })}
    </div>
  );
}
