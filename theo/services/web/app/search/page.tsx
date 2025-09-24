"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import { buildPassageLink, formatAnchor } from "../lib/api";

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
};

type SearchResponse = {
  results: SearchResult[];
};

const SOURCE_OPTIONS = [
  { label: "Any source", value: "" },
  { label: "PDF", value: "pdf" },
  { label: "Markdown", value: "markdown" },
  { label: "YouTube", value: "youtube" },
  { label: "Transcript", value: "transcript" },
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [osis, setOsis] = useState("");
  const [collection, setCollection] = useState("");
  const [author, setAuthor] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const filtersDescription = useMemo(() => {
    const parts: string[] = [];
    if (collection) parts.push(`Collection: ${collection}`);
    if (author) parts.push(`Author: ${author}`);
    if (sourceType) parts.push(`Source type: ${sourceType}`);
    return parts.join(" · ");
  }, [collection, author, sourceType]);

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
      const query = params.toString();
      const response = await fetch(`/api/search${query ? `?${query}` : ""}`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Search failed with status ${response.status}`);
      }
      const payload = (await response.json()) as SearchResponse;
      setResults(payload.results ?? []);
    } catch (error) {
      setError((error as Error).message);
      setResults([]);
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
          {isSearching ? "Searching…" : "Search"}
        </button>
      </form>

      {filtersDescription && <p>Active filters: {filtersDescription}</p>}
      {isSearching && <p role="status">Searching…</p>}
      {error && (
        <p role="alert" style={{ color: "crimson" }}>
          {error}
        </p>
      )}
      {!isSearching && hasSearched && !error && results.length === 0 && (
        <p>No results found for the current query.</p>
      )}

      <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "1rem" }}>
        {results.map((result) => {
          const anchorDescription = formatAnchor({
            page_no: result.page_no ?? undefined,
            t_start: result.t_start ?? undefined,
            t_end: result.t_end ?? undefined,
          });
          return (
            <li key={result.id} style={{ background: "#fff", padding: "1rem", borderRadius: "0.5rem" }}>
              <article>
                <header>
                  <h3 style={{ margin: "0 0 0.5rem" }}>{result.document_title ?? "Untitled document"}</h3>
                  {anchorDescription && <p style={{ margin: "0 0 0.25rem" }}>{anchorDescription}</p>}
                  {result.osis_ref && (
                    <p style={{ margin: 0 }}>OSIS: {result.osis_ref}</p>
                  )}
                </header>
                <p style={{ marginTop: "0.75rem" }}>{result.snippet}</p>
                <footer style={{ marginTop: "0.75rem", display: "flex", gap: "1rem" }}>
                  <Link
                    href={buildPassageLink(result.document_id, result.id, {
                      pageNo: result.page_no ?? undefined,
                      tStart: result.t_start ?? undefined,
                    })}
                  >
                    Open passage
                  </Link>
                  {typeof result.score === "number" && (
                    <span>Score: {result.score.toFixed(2)}</span>
                  )}
                </footer>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
