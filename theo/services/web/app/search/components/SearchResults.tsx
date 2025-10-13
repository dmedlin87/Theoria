"use client";

import Link from "next/link";
import VirtualList from "../../components/VirtualList";
import { buildPassageLink, formatAnchor } from "../../lib/api";
import type { DocumentGroup } from "../components/SearchPageClient";

interface SearchResultsProps {
  groups: DocumentGroup[];
  queryTokens: string[];
  onPassageClick: (result: { id: string; document_id: string; rank?: number | null }) => void;
}

function escapeRegExp(value: string): string {
  return value.replace(/[\^$.*+?()\[\]{}|]/g, "\\$&");
}

function highlightTokens(text: string, tokens: string[]): JSX.Element {
  if (!tokens.length) {
    return <>{text}</>;
  }
  const pattern = new RegExp(`(${tokens.map(escapeRegExp).join("|")})`, "gi");
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, index) =>
        tokens.some((token) => token.toLowerCase() === part.toLowerCase()) ? (
          <mark key={`${part}-${index}`}>{part}</mark>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        )
      )}
    </>
  );
}

export default function SearchResults({
  groups,
  queryTokens,
  onPassageClick,
}: SearchResultsProps): JSX.Element {
  if (groups.length === 0) {
    return (
      <div className="alert alert-info">
        <div className="alert__title">No results found</div>
        <div className="alert__message">
          Try adjusting your search query or filters to find what you&rsquo;re looking for.
        </div>
      </div>
    );
  }

  return (
    <VirtualList
      items={groups}
      itemKey={(group) => group.documentId}
      estimateSize={(group) => 220 + group.passages.length * 160}
      containerProps={{
        className: "search-results__scroller",
        "aria-label": "Search results",
      }}
      renderItem={(group, index) => {
        return (
          <div className="search-results__row stagger-item" data-last={index === groups.length - 1}>
            <article className="card card--interactive fade-in">
              <header className="stack-xs mb-3">
                <h3 className="text-xl font-semibold mb-0">{group.title}</h3>
                {group.score !== null && group.score !== undefined && (
                  <p className="text-sm text-muted mb-0">
                    Relevance: {Math.round(group.score * 100)}%
                  </p>
                )}
              </header>

              <div className="stack-md">
                {group.passages.map((passage) => {
              const anchor = formatAnchor({
                page_no: passage.page_no ?? null,
                t_start: passage.t_start ?? null,
                t_end: passage.t_end ?? null,
              });

              return (
                <div
                  key={passage.id}
                  className="panel"
                  style={{ padding: "var(--space-2)" }}
                >
                  <div className="stack-xs">
                    {passage.osis_ref && (
                      <p className="text-sm font-semibold text-accent mb-0">
                        {passage.osis_ref}
                      </p>
                    )}
                    {anchor && (
                      <p className="text-sm text-muted mb-0">{anchor}</p>
                    )}
                    <p className="mb-0">
                      {highlightTokens(passage.text, queryTokens)}
                    </p>
                    {passage.rank !== null && passage.rank !== undefined && (
                      <p className="text-xs text-muted mb-0">
                        Rank: {passage.rank}
                      </p>
                    )}
                  </div>

                  <div className="cluster-sm mt-2">
                    <Link
                      href={buildPassageLink(passage.document_id, passage.id, {
                        pageNo: passage.page_no ?? null,
                        tStart: passage.t_start ?? null,
                      })}
                      onClick={() =>
                        onPassageClick({
                          id: passage.id,
                          document_id: passage.document_id,
                          rank: passage.rank,
                        })
                      }
                      className="btn btn-secondary btn-sm"
                    >
                      Open document
                    </Link>
                  </div>
                </div>
              );
            })}
              </div>
            </article>
          </div>
        );
      }}
    />
  );
}
