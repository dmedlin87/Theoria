"use client";

import { FormEvent, useMemo, useState } from "react";

import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";

type GeoSearchResult = {
  name: string;
  osis: string;
  coordinates?: { lat: number; lng: number } | null;
  aliases?: string[] | null;
};

type GeoSearchResponse = {
  results?: GeoSearchResult[] | null;
};

interface GeoPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default function GeoPanel({ osis, features }: GeoPanelProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<GeoSearchResult[]>([]);
  const [submitted, setSubmitted] = useState(false);

  const { mode } = useMode();
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);

  if (!features?.geo) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);

    if (!query.trim()) {
      setError("Enter a location to search.");
      setResults([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${baseUrl}/research/geo/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), osis, mode: mode.id }),
      });
      if (!response.ok) {
        throw new Error((await response.text()) || response.statusText);
      }
      const payload = (await response.json()) as GeoSearchResponse;
      setResults(
        payload.results?.filter((item): item is GeoSearchResult => Boolean(item)) ?? [],
      );
    } catch (requestError) {
      console.error("Failed to run geo search", requestError);
      setError(requestError instanceof Error ? requestError.message : "Unknown error");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      aria-labelledby="geo-panel-heading"
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="geo-panel-heading" style={{ marginTop: 0 }}>
        Geographic context
      </h3>
      <p style={{ marginTop: 0 }}>
        Discover locations linked to <strong>{osis}</strong>.
      </p>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #64748b)", fontSize: "0.85rem" }}>{modeSummary}</p>
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: "0.75rem", marginBottom: "1rem" }}>
        <label style={{ display: "grid", gap: "0.5rem" }}>
          Search locations
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. Jerusalem"
            style={{ padding: "0.5rem", borderRadius: "0.375rem", border: "1px solid var(--border, #e5e7eb)" }}
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          {error}
        </p>
      ) : null}

      {!loading && submitted && !error && results.length === 0 ? (
        <p>No locations found.</p>
      ) : null}

      {results.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.75rem" }}>
          {results.map((item) => (
            <li
              key={`${item.name}-${item.osis}`}
              style={{ border: "1px solid var(--border, #e5e7eb)", borderRadius: "0.5rem", padding: "0.75rem" }}
            >
              <h4 style={{ margin: "0 0 0.25rem" }}>{item.name}</h4>
              <p style={{ margin: "0 0 0.25rem", fontSize: "0.875rem" }}>OSIS: {item.osis}</p>
              {item.coordinates ? (
                <p style={{ margin: "0 0 0.25rem", fontSize: "0.875rem" }}>
                  Coordinates: {item.coordinates.lat.toFixed(2)}, {item.coordinates.lng.toFixed(2)}
                </p>
              ) : null}
              {item.aliases && item.aliases.length > 0 ? (
                <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--muted-foreground, #4b5563)" }}>
                  Also known as: {item.aliases.join(", ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
