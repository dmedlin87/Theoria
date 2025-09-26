"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import { buildPassageLink, formatAnchor } from "../lib/api";

const SOURCE_OPTIONS = [
  { label: "Any source", value: "" },
  { label: "PDF", value: "pdf" },
  { label: "Markdown", value: "markdown" },
  { label: "YouTube", value: "youtube" },
  { label: "Transcript", value: "transcript" },
];

type SearchResult = {
  id: string;
  document_id: string;
  text: string;
  snippet: string;
  document_title?: string | null;
  osis_ref?: string | null;
  page_no?: number | null;
  t_start?: number | null;
  t_end?: number | null;
  score?: number | null;
  highlights?: string[] | null;
  document_score?: number | null;
  document_rank?: number | null;
};

type SearchResponse = {
  results: SearchResult[];
};

type DocumentGroup = {
  documentId: string;
  title: string;
  rank?: number | null;
  score?: number | null;
  passages: SearchResult[];
};

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

export default function SearchPage(): JSX.Element {
  const [query, setQuery] = useState("");
  const [osis, setOsis] = useState("");
  const [collection, setCollection] = useState("");
  const [author, setAuthor] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [groups, setGroups] = useState<DocumentGroup[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const filterChips = useMemo(() => {
    const chips: { label: string; value: string }[] = [];
    if (collection) chips.push({ label: "Collection", value: collection });
    if (author) chips.push({ label: "Author", value: author });
    if (sourceType) chips.push({ label: "Source", value: sourceType });
    return chips;
  }, [collection, author, sourceType]);

  const queryTokens = useMemo(() => {
    return query
      .split(/\s+/)
      .map((token) => token.trim())
      .filter(Boolean);
  }, [query]);

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSearching(true);
    setError(null);
    setHasSearched(true);

    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (osis.trim()) params.set("osis", osis.trim());
    if (collection.trim()) params.set("collection", collection.trim());
    if (author.trim()) params.set("author", author.trim());
    if (sourceType) params.set("source_type", sourceType);

    try {
      const searchQuery = params.toString();
      const response = await fetch(`/api/search${searchQuery ? `?${searchQuery}` : ""}`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Search failed with status ${response.status}`);
      }
      const payload = (await response.json()) as SearchResponse;
      const grouped = new Map<string, DocumentGroup>();
      for (const result of payload.results ?? []) {
        const group = grouped.get(result.document_id) ?? {
          documentId: result.document_id,
          title: result.document_title ?? "Untitled document",
          rank: result.document_rank,
          score: result.document_score ?? result.score ?? null,
          passages: [],
        };
        group.rank = group.rank ?? result.document_rank;
        const candidateScore = result.document_score ?? result.score ?? null;
        if (typeof candidateScore === "number") {
          if (typeof group.score !== "number" || candidateScore > group.score) {
            group.score = candidateScore;
          }
        }
        group.passages.push(result);
        grouped.set(result.document_id, group);
      }
      const sortedGroups = Array.from(grouped.values()).sort((a, b) => {
        if (a.rank && b.rank) return a.rank - b.rank;
        if (a.rank) return -1;
        if (b.rank) return 1;
        if (typeof b.score === "number" && typeof a.score === "number") {
          return b.score - a.score;
        }
        return a.title.localeCompare(b.title);
      });
      setGroups(sortedGroups);
    } catch (fetchError) {
      setError((fetchError as Error).message);
      setGroups([]);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <section>
      <h2>Search</h2>
      <p>Hybrid search with lexical, vector, and OSIS-aware filtering.</p>
      <form onSubmit={handleSearch} aria-label="Search corpus" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          <label style={{ display: "block" }}>
            Query
            <input
              name="q"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search corpus"
              style={{ width: "100%" }}
            />
          </label>
          <label style={{ display: "block" }}>
            OSIS reference
            <input
              name="osis"
              type="text"
              value={osis}
              onChange={(event) => setOsis(event.target.value)}
              placeholder="John.1.1-5"
              style={{ width: "100%" }}
            />
          </label>
          <label style={{ display: "block" }}>
            Collection
            <input
              name="collection"
              type="text"
              value={collection}
              onChange={(event) => setCollection(event.target.value)}
              placeholder="Gospels"
              style={{ width: "100%" }}
            />
          </label>
          <label style={{ display: "block" }}>
            Author
            <input
              name="author"
              type="text"
              value={author}
              onChange={(event) => setAuthor(event.target.value)}
              placeholder="Jane Doe"
              style={{ width: "100%" }}
            />
          </label>
          <label style={{ display: "block" }}>
            Source type
            <select
              name="source_type"
              value={sourceType}
              onChange={(event) => setSourceType(event.target.value)}
              style={{ width: "100%" }}
            >
              {SOURCE_OPTIONS.map((option) => (
                <option key={option.value || "any"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button type="submit" style={{ marginTop: "1rem" }} disabled={isSearching}>
          {isSearching ? "Searching." : "Search"}
        </button>
      </form>

      {filterChips.length > 0 && (
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
          {filterChips.map((chip) => (
            <span
              key={`${chip.label}-${chip.value}`}
              style={{
                background: "#e8eef9",
                borderRadius: "999px",
                padding: "0.25rem 0.75rem",
                fontSize: "0.85rem",
              }}
            >
              <strong>{chip.label}:</strong> {chip.value}
            </span>
          ))}
        </div>
      )}

      {isSearching && <p role="status">Searching.</p>}
      {error && (
        <p role="alert" style={{ color: "crimson" }}>
          {error}
        </p>
      )}
      {!isSearching && hasSearched && !error && groups.length === 0 && (
        <p>No results found for the current query.</p>
      )}

      <div style={{ display: "grid", gap: "1rem" }}>
        {groups.map((group) => (
          <article key={group.documentId} style={{ background: "#fff", borderRadius: "0.75rem", padding: "1.25rem" }}>
            <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem" }}>
              <div>
                <h3 style={{ margin: "0 0 0.25rem" }}>{group.title}</h3>
                {typeof group.rank === "number" && (
                  <p style={{ margin: 0 }}>Document rank #{group.rank}</p>
                )}
                {typeof group.score === "number" && (
                  <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "#555" }}>
                    Document score {group.score.toFixed(2)}
                  </p>
                )}
              </div>
            </header>
            <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0 0", display: "grid", gap: "0.75rem" }}>
              {group.passages.map((result) => {
                const anchorDescription = formatAnchor({
                  page_no: result.page_no ?? undefined,
                  t_start: result.t_start ?? undefined,
                  t_end: result.t_end ?? undefined,
                });
                return (
                  <li key={result.id} style={{ border: "1px solid #e2e8f0", borderRadius: "0.5rem", padding: "0.75rem" }}>
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
                        <div>
                          {anchorDescription && <p style={{ margin: "0 0 0.25rem" }}>{anchorDescription}</p>}
                          {result.osis_ref && <p style={{ margin: 0 }}>OSIS: {result.osis_ref}</p>}
                        </div>
                        <Link
                          href={buildPassageLink(result.document_id, result.id, {
                            pageNo: result.page_no ?? undefined,
                            tStart: result.t_start ?? undefined,
                          })}
                          style={{ whiteSpace: "nowrap" }}
                        >
                          Open passage
                        </Link>
                      </div>
                      <p style={{ marginTop: "0.5rem" }}>{result.snippet}</p>
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
                              {highlightTokens(highlight, queryTokens)}
                            </p>
                          ))}
                        </div>
                      )}
                      {typeof result.score === "number" && (
                        <p style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "#555" }}>
                          Passage score {result.score.toFixed(2)}
                        </p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}
