"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  type ResearchMode,
  formatEmphasisSummary,
} from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "../types";

const MAX_COMPARISON_SELECTIONS = 2;

interface ManuscriptMetadata {
  name?: string | null;
  siglum?: string | null;
  date?: string | null;
  provenance?: string | null;
}

interface VariantReading {
  id: string;
  osis: string;
  category: string;
  reading: string;
  note?: string | null;
  source?: string | null;
  witness?: string | null;
  translation?: string | null;
  confidence?: number | null;
  disputed?: boolean | null;
  dataset?: string | null;
  witness_metadata?: ManuscriptMetadata | null;
}

interface VariantApparatusResponse {
  osis: string;
  readings?: VariantReading[] | null;
  total?: number | null;
}

interface DssLink {
  id: string;
  osis: string;
  title: string;
  url: string;
  fragment?: string | null;
  summary?: string | null;
  dataset?: string | null;
}

interface DssLinksResponse {
  osis: string;
  links?: DssLink[] | null;
  total?: number | null;
}

type ChronologyPoint = {
  id: string;
  label: string;
  year: number;
  dateLabel: string | null;
  disputed: boolean;
};

type ComparisonRow = {
  label: string;
  render: (reading: VariantReading, context: { index: number; all: VariantReading[] }) => ReactNode;
};

function normalizeBaseUrl(): string {
  return getApiBaseUrl().replace(/\/$/, "");
}

function readingDisplayName(reading: VariantReading): string {
  return (
    reading.witness_metadata?.name ||
    reading.witness ||
    reading.translation ||
    reading.category
  );
}

function formatList(items: Array<string | null | undefined>): string {
  const filtered = items.filter((item): item is string => Boolean(item && item.trim()));
  if (filtered.length === 0) return "";
  if (filtered.length === 1) {
    return filtered[0]!;
  }
  if (filtered.length === 2) {
    return `${filtered[0]!} and ${filtered[1]!}`;
  }
  const [last, ...restReversed] = filtered.slice().reverse();
  const rest = restReversed.reverse();
  return `${rest.join(", ")}, and ${last}`;
}

function parseYear(value?: string | null): number | null {
  if (!value) return null;
  const normalized = value.trim().toLowerCase();
  const match = normalized.match(/(-?\d{1,4})/);
  const yearGroup = match?.[1];
  if (!yearGroup) return null;
  const raw = Number.parseInt(yearGroup, 10);
  if (Number.isNaN(raw)) return null;
  if (normalized.includes("bc") || normalized.includes("bce")) {
    return -Math.abs(raw);
  }
  return raw;
}

function formatYearLabel(year: number): string {
  if (year < 0) return `${Math.abs(year)} BCE`;
  if (year === 0) return "1 CE";
  return `${year} CE`;
}

function computeChronology(readings: VariantReading[]): ChronologyPoint[] {
  const points: ChronologyPoint[] = [];
  readings.forEach((reading) => {
    const meta = reading.witness_metadata;
    if (!meta) return;
    const year = parseYear(meta.date);
    if (year === null) return;
    points.push({
      id: reading.id,
      label: readingDisplayName(reading),
      year,
      dateLabel: meta.date ?? null,
      disputed: reading.disputed === true,
    });
  });
  points.sort((a, b) => a.year - b.year);
  return points;
}

function buildSummary(readings: VariantReading[], mode: ResearchMode): string | null {
  const manuscripts = readings.filter(
    (reading) => reading.category.toLowerCase() === "manuscript",
  );
  if (manuscripts.length === 0) {
    return null;
  }

  const sorted = manuscripts
    .slice()
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  const mainstream = sorted.find((reading) => reading.disputed !== true) ?? sorted[0];
  if (!mainstream) {
    return null;
  }

  const mainstreamWitnesses = sorted
    .filter((reading) => reading.disputed !== true && reading.reading === mainstream.reading)
    .map(readingDisplayName)
    .filter(Boolean);

  const alternatives = manuscripts
    .filter((reading) => reading.id !== mainstream.id)
    .map((reading) => ({
      descriptor: `${readingDisplayName(reading)} (“${reading.reading}”)`,
      disputed: reading.disputed === true,
    }));

  const summaryParts: string[] = [];
  if (mainstreamWitnesses.length > 0) {
    summaryParts.push(
      `Mainstream witnesses like ${formatList(mainstreamWitnesses)} support “${mainstream.reading}”.`,
    );
  } else {
    summaryParts.push(`The strongest manuscript evidence favours “${mainstream.reading}”.`);
  }

  if (alternatives.length > 0) {
    const alternativeDescriptions = alternatives.map((entry) => entry.descriptor);
    summaryParts.push(
      `Alternate readings surface in ${formatList(alternativeDescriptions)}.`,
    );
  }

  if (mode.id === "investigative") {
    summaryParts.push(
      "Investigative mode highlights these tensions for deeper textual comparison.",
    );
  } else if (mode.id === "devotional") {
    summaryParts.push(
      "Devotional mode treats the mainstream reading as the stable baseline while noting alternatives for reflection.",
    );
  }

  return summaryParts.join(" ");
}

function highlightDifference(
  value: string | null | undefined,
  all: VariantReading[],
  accessor: (reading: VariantReading) => string | null | undefined,
): ReactNode {
  if (!value) {
    return <span style={{ color: "var(--muted-foreground, #64748b)" }}>—</span>;
  }
  const differs = all.some((reading) => accessor(reading) !== value);
  const style = differs
    ? {
        background: "rgba(248, 113, 113, 0.2)",
        borderRadius: "0.35rem",
        padding: "0.125rem 0.35rem",
        display: "inline-block",
      }
    : undefined;
  return <span style={style}>{value}</span>;
}

export default function TextualVariantsPanel({
  osis,
  features,
}: {
  osis: string;
  features: ResearchFeatureFlags;
}): JSX.Element | null {
  const { mode } = useMode();
  const baseUrl = useMemo(normalizeBaseUrl, []);
  const [readings, setReadings] = useState<VariantReading[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showDisputedOnly, setShowDisputedOnly] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [selectedWitnesses, setSelectedWitnesses] = useState<string[]>([]);
  const [dssLinks, setDssLinks] = useState<DssLink[]>([]);
  const [dssError, setDssError] = useState<string | null>(null);
  const [dssLoading, setDssLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!features?.textual_variants) {
      return;
    }
    const controller = new AbortController();

    async function loadData() {
      setLoading(true);
      setError(null);
      setDssLoading(true);
      setDssError(null);

      try {
        const dssResponse = await fetch(
          `${baseUrl}/research/dss-links?osis=${encodeURIComponent(osis)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (dssResponse.ok) {
          const payload = (await dssResponse.json()) as DssLinksResponse;
          const links = payload.links?.filter((link): link is DssLink => Boolean(link)) ?? [];
          setDssLinks(links);
        } else if (!controller.signal.aborted) {
          const message = (await dssResponse.text()) || dssResponse.statusText;
          setDssError(message);
          setDssLinks([]);
        }
      } catch (linkError) {
        if (!(linkError instanceof DOMException && linkError.name === "AbortError")) {
          setDssError(linkError instanceof Error ? linkError.message : "Failed to load DSS links");
        }
      } finally {
        if (!controller.signal.aborted) {
          setDssLoading(false);
        }
      }

      try {
        const response = await fetch(
          `${baseUrl}/research/variants?osis=${encodeURIComponent(osis)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (!response.ok) {
          throw new Error((await response.text()) || response.statusText);
        }
        const payload = (await response.json()) as VariantApparatusResponse;
        const entries = payload.readings?.filter(
          (reading): reading is VariantReading => Boolean(reading),
        );
        setReadings(entries ?? []);
      } catch (fetchError) {
        if (fetchError instanceof DOMException && fetchError.name === "AbortError") {
          return;
        }
        console.error("Failed to load textual variants", fetchError);
        setError(fetchError instanceof Error ? fetchError.message : "Unknown error");
        setReadings([]);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadData();

    return () => {
      controller.abort();
    };
  }, [baseUrl, features?.textual_variants, osis]);

  useEffect(() => {
    setSelectedWitnesses((current) =>
      current.filter((id) => readings.some((reading) => reading.id === id)),
    );
  }, [readings]);

  const toggleWitnessSelection = useCallback((readingId: string) => {
    setSelectedWitnesses((current) => {
      if (current.includes(readingId)) {
        return current.filter((id) => id !== readingId);
      }
      if (current.length >= MAX_COMPARISON_SELECTIONS) {
        return [...current.slice(1), readingId];
      }
      return [...current, readingId];
    });
  }, []);

  const clearComparison = useCallback(() => setSelectedWitnesses([]), []);

  const categoryOptions = useMemo(() => {
    const counts = new Map<string, number>();
    readings.forEach((reading) => {
      const key = reading.category.toLowerCase();
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return Array.from(counts.entries()).map(([value, count]) => ({
      value,
      label: `${value.charAt(0).toUpperCase()}${value.slice(1)} (${count})`,
    }));
  }, [readings]);

  const filteredReadings = useMemo(() => {
    return readings.filter((reading) => {
      if (showDisputedOnly && reading.disputed !== true) {
        return false;
      }
      if (
        categoryFilter !== "all" &&
        reading.category.toLowerCase() !== categoryFilter.toLowerCase()
      ) {
        return false;
      }
      return true;
    });
  }, [readings, showDisputedOnly, categoryFilter]);

  const chronology = useMemo(
    () => computeChronology(readings.filter((reading) => reading.category.toLowerCase() === "manuscript")),
    [readings],
  );

  const summary = useMemo(() => buildSummary(readings, mode), [readings, mode]);
  const [firstDssLink, ...otherDssLinks] = dssLinks;

  const selectedReadings = useMemo(
    () =>
      selectedWitnesses
        .map((id) => readings.find((reading) => reading.id === id))
        .filter((reading): reading is VariantReading => Boolean(reading)),
    [readings, selectedWitnesses],
  );

  const comparisonRows: ComparisonRow[] = useMemo(
    () => [
      {
        label: "Witness",
        render: (reading) => readingDisplayName(reading),
      },
      {
        label: "Reading",
        render: (reading, context) =>
          highlightDifference(reading.reading, context.all, (candidate) => candidate.reading),
      },
      {
        label: "Category",
        render: (reading, context) =>
          highlightDifference(reading.category, context.all, (candidate) => candidate.category),
      },
      {
        label: "Translation",
        render: (reading, context) =>
          highlightDifference(
            reading.translation ?? null,
            context.all,
            (candidate) => candidate.translation ?? null,
          ),
      },
      {
        label: "Dataset",
        render: (reading, context) =>
          highlightDifference(
            reading.dataset ?? null,
            context.all,
            (candidate) => candidate.dataset ?? null,
          ),
      },
      {
        label: "Confidence",
        render: (reading, context) =>
          highlightDifference(
            reading.confidence != null ? `${Math.round(reading.confidence * 100)}%` : null,
            context.all,
            (candidate) =>
              candidate.confidence != null
                ? `${Math.round(candidate.confidence * 100)}%`
                : null,
          ),
      },
      {
        label: "Disputed",
        render: (reading, context) =>
          highlightDifference(
            reading.disputed ? "Yes" : "No",
            context.all,
            (candidate) => (candidate.disputed ? "Yes" : "No"),
          ),
      },
      {
        label: "Note",
        render: (reading, context) =>
          highlightDifference(
            reading.note ?? null,
            context.all,
            (candidate) => candidate.note ?? null,
          ),
      },
      {
        label: "Source",
        render: (reading, context) =>
          highlightDifference(
            reading.source ?? null,
            context.all,
            (candidate) => candidate.source ?? null,
          ),
      },
      {
        label: "Date",
        render: (reading, context) =>
          highlightDifference(
            reading.witness_metadata?.date ?? null,
            context.all,
            (candidate) => candidate.witness_metadata?.date ?? null,
          ),
      },
      {
        label: "Provenance",
        render: (reading, context) =>
          highlightDifference(
            reading.witness_metadata?.provenance ?? null,
            context.all,
            (candidate) => candidate.witness_metadata?.provenance ?? null,
          ),
      },
    ],
    [],
  );

  const firstChronology = chronology[0] ?? null;
  const lastChronology = chronology.length > 0 ? chronology[chronology.length - 1] ?? null : null;
  const minYear = firstChronology ? firstChronology.year : null;
  const maxYear = lastChronology ? lastChronology.year : null;
  const span = minYear !== null && maxYear !== null ? Math.max(maxYear - minYear, 1) : 1;

  if (!features?.textual_variants) {
    return null;
  }

  return (
    <section
      aria-labelledby="textual-variants-heading"
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="textual-variants-heading" style={{ marginTop: 0 }}>
        Textual variants
      </h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        Compare witness readings for <strong>{osis}</strong> with timeline and commentary cues.
      </p>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #64748b)", fontSize: "0.875rem" }}>
        {formatEmphasisSummary(mode)}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
        {dssLoading ? (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              fontSize: "0.8rem",
              color: "var(--muted-foreground, #64748b)",
            }}
          >
            Checking Dead Sea Scrolls links…
          </span>
        ) : null}
        {firstDssLink ? (
          <div style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
            <a
              href={firstDssLink.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.35rem",
                padding: "0.35rem 0.75rem",
                borderRadius: "999px",
                background: "#e0f2fe",
                color: "#0f172a",
                textDecoration: "none",
                fontWeight: 600,
              }}
              title={otherDssLinks
                .map((link) => link.title || link.fragment || link.url)
                .filter((entry): entry is string => Boolean(entry))
                .join("\n")}
            >
              Dead Sea Scrolls
              <span
                style={{
                  background: "#0ea5e9",
                  color: "#fff",
                  borderRadius: "999px",
                  padding: "0.1rem 0.5rem",
                  fontSize: "0.75rem",
                }}
              >
                {dssLinks.length}
              </span>
            </a>
            {otherDssLinks.length > 0 ? (
              <details style={{ fontSize: "0.8rem" }}>
                <summary style={{ cursor: "pointer" }}>More fragments</summary>
                <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem" }}>
                  {otherDssLinks.map((link) => (
                    <li key={link.id}>
                      <a href={link.url} target="_blank" rel="noopener noreferrer">
                        {link.fragment || link.title || link.url}
                      </a>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        ) : null}
        {dssError ? (
          <span style={{ color: "#b91c1c", fontSize: "0.8rem" }}>
            DSS links unavailable: {dssError}
          </span>
        ) : null}
      </div>

      {summary ? (
        <aside
          aria-label="Variant summary"
          style={{
            marginTop: "1rem",
            background: "var(--muted, #f8fafc)",
            borderRadius: "0.5rem",
            padding: "0.75rem",
            border: "1px solid var(--border, #e5e7eb)",
          }}
        >
          <strong style={{ display: "block", marginBottom: "0.25rem" }}>
            Mainstream vs. competing readings
          </strong>
          <p style={{ margin: 0, lineHeight: 1.6 }}>{summary}</p>
        </aside>
      ) : null}

      {selectedReadings.length > 0 ? (
        <aside
          style={{
            marginTop: "1.5rem",
            border: "1px solid #cbd5f5",
            borderRadius: "0.75rem",
            padding: "1rem",
            background: "#eef2ff",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "1rem",
              flexWrap: "wrap",
            }}
          >
            <h4 style={{ margin: 0 }}>Comparison workspace</h4>
            <button type="button" onClick={clearComparison}>
              Clear selection
            </button>
          </div>
          {selectedReadings.length < MAX_COMPARISON_SELECTIONS ? (
            <p style={{ margin: "0.5rem 0", fontSize: "0.85rem", color: "#4b5563" }}>
              Select another witness to complete the side-by-side comparison.
            </p>
          ) : null}
          <div style={{ overflowX: "auto", marginTop: "0.75rem" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                minWidth: "460px",
              }}
            >
              <thead>
                <tr>
                  <th
                    scope="col"
                    style={{
                      textAlign: "left",
                      padding: "0.5rem",
                      borderBottom: "2px solid rgba(99, 102, 241, 0.4)",
                      fontSize: "0.85rem",
                      color: "#312e81",
                    }}
                  >
                    Attribute
                  </th>
                  {selectedReadings.map((reading) => (
                    <th
                      key={reading.id}
                      scope="col"
                      style={{
                        textAlign: "left",
                        padding: "0.5rem",
                        borderBottom: "2px solid rgba(99, 102, 241, 0.4)",
                        fontSize: "0.85rem",
                        color: "#312e81",
                      }}
                    >
                      {readingDisplayName(reading)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row.label}>
                    <th
                      scope="row"
                      style={{
                        textAlign: "left",
                        padding: "0.5rem",
                        fontSize: "0.8rem",
                        color: "#4338ca",
                        borderBottom: "1px solid rgba(148, 163, 184, 0.35)",
                        background: "rgba(129, 140, 248, 0.08)",
                      }}
                    >
                      {row.label}
                    </th>
                    {selectedReadings.map((reading, index) => (
                      <td
                        key={`${reading.id}-${row.label}`}
                        style={{
                          padding: "0.5rem",
                          fontSize: "0.85rem",
                          borderBottom: "1px solid rgba(226, 232, 240, 0.9)",
                        }}
                      >
                        {row.render(reading, { index, all: selectedReadings })}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </aside>
      ) : null}
      <div
        style={{
          marginTop: "1.25rem",
          display: "flex",
          flexWrap: "wrap",
          gap: "0.75rem",
          alignItems: "center",
        }}
      >
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={showDisputedOnly}
            onChange={(event) => setShowDisputedOnly(event.target.checked)}
          />
          Disputed readings only
        </label>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          Category
          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
            style={{ padding: "0.25rem 0.5rem" }}
          >
            <option value="all">All categories ({readings.length})</option>
            {categoryOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <p style={{ marginTop: "1rem" }}>Loading textual variants…</p>
      ) : error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)", marginTop: "1rem" }}>
          Unable to load textual variants. {error}
        </p>
      ) : readings.length === 0 ? (
        <p style={{ marginTop: "1rem" }}>No textual variants available.</p>
      ) : (
        <div style={{ display: "grid", gap: "1.25rem", marginTop: "1rem" }}>
          {chronology.length > 0 ? (
            <div>
              <h4 style={{ margin: "0 0 0.5rem" }}>Manuscript chronology</h4>
              <div
                aria-hidden="true"
                style={{
                  position: "relative",
                  height: "2px",
                  background: "#e2e8f0",
                  borderRadius: "999px",
                  marginBottom: "0.75rem",
                }}
              >
                {chronology.map((point) => {
                  const ratio =
                    minYear !== null
                      ? Math.min(Math.max((point.year - minYear) / span, 0), 1)
                      : 0.5;
                  return (
                    <span
                      key={point.id}
                      title={`${point.label}${point.dateLabel ? ` · ${point.dateLabel}` : ""}`}
                      style={{
                        position: "absolute",
                        left: `calc(${ratio * 100}% - 6px)`,
                        top: "-5px",
                        width: "12px",
                        height: "12px",
                        borderRadius: "999px",
                        background: point.disputed ? "#b91c1c" : "#2563eb",
                        border: "2px solid #fff",
                        boxShadow: "0 0 0 1px rgba(15, 23, 42, 0.1)",
                      }}
                    />
                  );
                })}
              </div>
              <ul
                style={{
                  listStyle: "none",
                  padding: 0,
                  margin: 0,
                  display: "grid",
                  gap: "0.5rem",
                }}
              >
                {chronology.map((point) => (
                  <li
                    key={`${point.id}-chronology`}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: "1rem",
                      fontSize: "0.875rem",
                      color: "var(--muted-foreground, #4b5563)",
                    }}
                  >
                    <span>
                      <strong style={{ color: "#1f2937" }}>
                        {point.dateLabel ?? formatYearLabel(point.year)}
                      </strong>
                      {point.disputed ? " · disputed" : ""}
                    </span>
                    <span>{point.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {filteredReadings.length === 0 ? (
            <p>No variants match the current filters.</p>
          ) : (
            <div style={{ display: "grid", gap: "1rem" }}>
              {filteredReadings.map((reading) => {
                const isSelected = selectedWitnesses.includes(reading.id);
                const compareLabel = isSelected
                  ? "Remove from compare"
                  : selectedWitnesses.length >= MAX_COMPARISON_SELECTIONS
                  ? "Replace in compare"
                  : "Add to compare";
                const confidenceLabel =
                  typeof reading.confidence === "number"
                    ? `${Math.round(reading.confidence * 100)}% confidence`
                    : null;
                return (
                  <article
                    key={reading.id}
                    style={{
                      border: isSelected
                        ? "2px solid rgba(59, 130, 246, 0.8)"
                        : "1px solid var(--border, #e5e7eb)",
                      borderRadius: "0.75rem",
                      padding: "0.75rem",
                      background: "var(--muted, #f8fafc)",
                    }}
                  >
                    <header style={{ marginBottom: "0.5rem" }}>
                      <div
                        style={{
                          display: "flex",
                          gap: "0.5rem",
                          alignItems: "baseline",
                          flexWrap: "wrap",
                          justifyContent: "space-between",
                        }}
                      >
                        <div style={{ display: "grid", gap: "0.35rem" }}>
                          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                            <strong>{readingDisplayName(reading)}</strong>
                            <span
                              style={{
                                fontSize: "0.875rem",
                                color: "var(--muted-foreground, #4b5563)",
                              }}
                            >
                              {reading.category}
                              {reading.translation ? ` · ${reading.translation}` : ""}
                            </span>
                          </div>
                          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                            {reading.dataset ? (
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "0.25rem",
                                  background: "#dbeafe",
                                  color: "#1d4ed8",
                                  fontSize: "0.75rem",
                                  padding: "0.125rem 0.5rem",
                                  borderRadius: "999px",
                                }}
                              >
                                {reading.dataset}
                              </span>
                            ) : null}
                            {reading.disputed ? (
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "0.25rem",
                                  background: "#fee2e2",
                                  color: "#991b1b",
                                  fontSize: "0.75rem",
                                  padding: "0.125rem 0.5rem",
                                  borderRadius: "999px",
                                }}
                              >
                                Disputed
                              </span>
                            ) : null}
                            {confidenceLabel ? (
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "0.25rem",
                                  background: "#ede9fe",
                                  color: "#5b21b6",
                                  fontSize: "0.75rem",
                                  padding: "0.125rem 0.5rem",
                                  borderRadius: "999px",
                                }}
                              >
                                {confidenceLabel}
                              </span>
                            ) : null}
                            {reading.witness_metadata?.date ? (
                              <span
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "0.25rem",
                                  background: "#fef3c7",
                                  color: "#b45309",
                                  fontSize: "0.75rem",
                                  padding: "0.125rem 0.5rem",
                                  borderRadius: "999px",
                                }}
                              >
                                {reading.witness_metadata.date}
                              </span>
                            ) : null}
                          </div>
                        </div>
                        <button type="button" onClick={() => toggleWitnessSelection(reading.id)}>
                          {compareLabel}
                        </button>
                      </div>
                    </header>
                    <p style={{ margin: "0 0 0.5rem", lineHeight: 1.6 }}>{reading.reading}</p>
                    {reading.note ? (
                      <p
                        style={{
                          margin: 0,
                          fontSize: "0.875rem",
                          color: "var(--muted-foreground, #4b5563)",
                          lineHeight: 1.6,
                        }}
                      >
                        {reading.note}
                      </p>
                    ) : null}
                    <footer
                      style={{
                        marginTop: "0.75rem",
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "0.75rem",
                        fontSize: "0.875rem",
                        color: "var(--muted-foreground, #4b5563)",
                      }}
                    >
                      {reading.source ? <span>Source: {reading.source}</span> : null}
                      {reading.witness_metadata?.provenance ? (
                        <span>Provenance: {reading.witness_metadata.provenance}</span>
                      ) : null}
                      {reading.witness_metadata?.siglum ? (
                        <span>Siglum: {reading.witness_metadata.siglum}</span>
                      ) : null}
                    </footer>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
