"use client";

import { FormEvent, useMemo, useState } from "react";

import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";

type GeoPlaceItem = {
  slug?: string | null;
  name?: string | null;
  lat?: number | null;
  lng?: number | null;
  aliases?: string[] | null;
};

type GeoSearchResponse = {
  items: GeoPlaceItem[];
};

interface GeoPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default function GeoPanel({ osis, features }: GeoPanelProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<GeoPlaceItem[]>([]);
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
      const params = new URLSearchParams({ query: query.trim() });
      const response = await fetch(
        `${baseUrl}/research/geo/search?${params.toString()}`,
        {
          method: "GET",
        },
      );
      if (!response.ok) {
        throw new Error((await response.text()) || response.statusText);
      }
      const payload = (await response.json()) as GeoSearchResponse;
      setResults(Array.isArray(payload.items) ? payload.items : []);
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
          {results.map((item, index) => {
            const identifier = item.slug || item.name || `geo-result-${index}`;
            const lat = typeof item.lat === "number" ? item.lat : null;
            const lng = typeof item.lng === "number" ? item.lng : null;

            return (
              <li
                key={identifier}
                style={{ border: "1px solid var(--border, #e5e7eb)", borderRadius: "0.5rem", padding: "0.75rem" }}
              >
                <h4 style={{ margin: "0 0 0.25rem" }}>{item.name ?? "Unknown location"}</h4>
                {lat !== null && lng !== null ? (
                  <p style={{ margin: "0 0 0.25rem", fontSize: "0.875rem" }}>
                    Coordinates: {lat.toFixed(2)}, {lng.toFixed(2)}
                  </p>
                ) : null}
                {item.aliases && item.aliases.length > 0 ? (
                  <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--muted-foreground, #4b5563)" }}>
                    Also known as: {item.aliases.join(", ")}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
