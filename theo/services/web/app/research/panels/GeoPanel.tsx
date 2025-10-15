"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import styles from "./GeoPanel.module.css";

import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "../types";

type GeoPlaceItem = {
  modern_id?: string | null;
  slug?: string | null;
  name: string;
  lat?: number | null;
  lng?: number | null;
  geom_kind?: string | null;
  confidence?: number | null;
  aliases?: string[] | null;
  sources?: {
    dataset?: string | null;
    license?: string | null;
  } | null;
};

type GeoSearchResponse = {
  items?: GeoPlaceItem[];
  // Support legacy responses returned before the GET migration landed on the API.
  results?: Array<
    GeoPlaceItem & {
      osis?: string | null;
      coordinates?: {
        lat?: number | null;
        lng?: number | null;
      } | null;
    }
  >;
};

type GeoLocationDetail = {
  modern_id: string;
  friendly_id: string;
  latitude?: number | null;
  longitude?: number | null;
  geom_kind?: string | null;
  confidence?: number | null;
  names?: string[] | null;
};

type GeoPlaceOccurrence = {
  ancient_id: string;
  friendly_id: string;
  classification?: string | null;
  osis_refs: string[];
  modern_locations: GeoLocationDetail[];
};

type GeoAttribution = {
  source: string;
  url: string;
  license: string;
  commit_sha?: string | null;
  osm_required?: boolean | null;
};

type GeoVerseResponse = {
  osis: string;
  places: GeoPlaceOccurrence[];
  attribution?: GeoAttribution | null;

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
  const [verseData, setVerseData] = useState<GeoVerseResponse | null>(null);
  const [verseLoading, setVerseLoading] = useState(true);
  const [verseError, setVerseError] = useState<string | null>(null);

  const { mode } = useMode();
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);

  useEffect(() => {
    if (!features?.geo) {
      return;
    }
    let cancelled = false;
    const run = async () => {
      setVerseLoading(true);
      setVerseError(null);
      try {
        const params = new URLSearchParams({ osis });
        const response = await fetch(
          `${baseUrl}/research/geo/verse?${params.toString()}`,
          { method: "GET" },
        );
        if (!response.ok) {
          throw new Error((await response.text()) || response.statusText);
        }
        const payload = (await response.json()) as GeoVerseResponse;
        if (!cancelled) {
          setVerseData(payload);
        }
      } catch (requestError) {
        if (!cancelled) {
          console.error("Failed to load verse geodata", requestError);
          setVerseError(requestError instanceof Error ? requestError.message : "Unknown error");
          setVerseData(null);
        }
      } finally {
        if (!cancelled) {
          setVerseLoading(false);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [baseUrl, features?.geo, osis]);

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
      const response = await fetch(`${baseUrl}/research/geo/search?${params.toString()}`, {
        method: "GET",
      });
      if (!response.ok) {
        throw new Error((await response.text()) || response.statusText);
      }
      const payload = (await response.json()) as GeoSearchResponse;
      const items: GeoPlaceItem[] = Array.isArray(payload.items)
        ? payload.items
        : Array.isArray(payload.results)
          ? payload.results.map((item) => {
              const lat = item.lat ?? item.coordinates?.lat ?? null;
              const lng = item.lng ?? item.coordinates?.lng ?? null;

              const normalized: GeoPlaceItem = {
                slug: item.slug ?? item.osis ?? null,
                name: item.name ?? item.osis ?? null,
                aliases: Array.isArray(item.aliases) ? item.aliases : null,
                confidence: item.confidence ?? null,
                sources: item.sources ?? null,
                lat: typeof lat === "number" ? lat : null,
                lng: typeof lng === "number" ? lng : null,
              };

              return normalized;
            })
          : [];

      setResults(items);
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
      className={styles.panel}
    >
      <h3 id="geo-panel-heading" className={styles.panelHeading}>
        Geographic context
      </h3>
      <p className={styles.description}>
        Discover locations linked to <strong>{osis}</strong>.
      </p>
      <p className={styles.modeSummary}>{modeSummary}</p>
      {verseLoading ? (
        <p>Loading locations mentioned in this verse…</p>
      ) : null}
      {verseError ? (
        <p role="alert" className={styles.errorMessage}>
          {verseError}
        </p>
      ) : null}
      {!verseLoading && !verseError ? (
        <div className={styles.versePlacesSection}>
          <h4 className={styles.sectionTitle}>Places linked to this verse</h4>
          {verseData?.places && verseData.places.length > 0 ? (
            <ul className={styles.placesList}>
              {verseData.places.map((place) => (
                <li
                  key={place.ancient_id}
                  className={styles.placeCard}
                >
                  <h4 className={styles.placeTitle}>{place.friendly_id}</h4>
                  {place.classification ? (
                    <p className={styles.placeClassification}>
                      Classification: {place.classification}
                    </p>
                  ) : null}
                  {place.modern_locations.length > 0 ? (
                    <ul className={styles.locationsList}>
                      {place.modern_locations.map((location) => {
                        const lat =
                          typeof location.latitude === "number"
                            ? location.latitude.toFixed(2)
                            : null;
                        const lng =
                          typeof location.longitude === "number"
                            ? location.longitude.toFixed(2)
                            : null;
                        return (
                          <li key={location.modern_id} className={styles.locationItem}>
                            <strong>{location.friendly_id}</strong>
                            {lat && lng ? (
                              <span>
                                {" "}
                                ({lat}, {lng})
                              </span>
                            ) : null}
                            {location.names && location.names.length > 0 ? (
                              <div className={styles.locationAliases}>
                                Also known as: {location.names.join(", ")}
                              </div>
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className={styles.noLocations}>
                      No modern locations are linked to this place yet.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.emptyState}>No catalogued places reference this verse yet.</p>
          )}
          {verseData?.attribution ? (
            <div className={styles.attribution}>
              <p className={styles.attributionText}>
                Geodata ©{" "}
                <a
                  href={verseData.attribution.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {verseData.attribution.source}
                </a>{" "}
                — Licensed {verseData.attribution.license}
                {verseData.attribution.commit_sha
                  ? ` (commit ${verseData.attribution.commit_sha.slice(0, 7)})`
                  : ""}
              </p>
              {verseData.attribution.osm_required ? (
                <p className={styles.attributionText}>
                  Shapes ©{' '}
                  <a
                    href="https://www.openstreetmap.org/copyright"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    OpenStreetMap contributors
                  </a>{" "}
                  — Licensed ODbL
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className={styles.searchForm}>
        <label className={styles.searchLabel}>
          Search locations
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. Jerusalem"
            className={styles.searchInput}
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error ? (
        <p role="alert" className={styles.errorMessage}>
          {error}
        </p>
      ) : null}

      {!loading && submitted && !error && results.length === 0 ? (
        <p>No locations found.</p>
      ) : null}

      {results.length > 0 && (
        <ul className={styles.resultsList}>
          {results.map((item, index) => {
            const identifier = item.modern_id || item.slug || item.name || `geo-result-${index}`;
            const lat = typeof item.lat === "number" ? item.lat : null;
            const lng = typeof item.lng === "number" ? item.lng : null;

            return (
              <li
                key={identifier}
                className={styles.resultCard}
              >
                <h4 className={styles.resultTitle}>{item.name ?? "Unknown location"}</h4>
                {lat !== null && lng !== null ? (
                  <p className={styles.coordinates}>
                    Coordinates: {lat.toFixed(2)}, {lng.toFixed(2)}
                  </p>
                ) : null}
                {item.aliases && item.aliases.length > 0 ? (
                  <p className={styles.aliases}>
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

