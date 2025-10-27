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
import styles from "./TextualVariantsPanel.module.css";

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

  if (mode.id === "critic") {
    summaryParts.push(
      "Critic mode highlights these tensions for deeper textual comparison.",
    );
  } else if (mode.id === "apologist") {
    summaryParts.push(
      "Apologist mode foregrounds the mainstream reading while noting alternatives that may need harmonisation.",
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
    return <span className={styles.highlightPlaceholder}>—</span>;
  }
  const differs = all.some((reading) => accessor(reading) !== value);
  return <span className={differs ? styles.highlightDifferent : undefined}>{value}</span>;
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
      className={styles.panel}
    >
      <h3 id="textual-variants-heading" className={styles.heading}>
        Textual variants
      </h3>
      <p className={styles.description}>
        Compare witness readings for <strong>{osis}</strong> with timeline and commentary cues.
      </p>
      <p className={styles.modeInfo}>
        {formatEmphasisSummary(mode)}
      </p>
      <div className={styles.dssLinks}>
        {dssLoading ? (
          <span className={styles.dssLoading}>
            Checking Dead Sea Scrolls links…
          </span>
        ) : null}
        {firstDssLink ? (
          <div className={styles.dssLinkWrapper}>
            <a
              href={firstDssLink.url}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.dssLink}
              title={otherDssLinks
                .map((link) => link.title || link.fragment || link.url)
                .filter((entry): entry is string => Boolean(entry))
                .join("\n")}
            >
              Dead Sea Scrolls
              <span className={styles.dssCount}>
                {dssLinks.length}
              </span>
            </a>
            {otherDssLinks.length > 0 ? (
              <details className={styles.dssDetails}>
                <summary className={styles.dssDetailsSummary}>More fragments</summary>
                <ul className={styles.dssDetailsList}>
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
          <span className={styles.dssError}>
            DSS links unavailable: {dssError}
          </span>
        ) : null}
      </div>

      {summary ? (
        <aside
          aria-label="Variant summary"
          className={styles.summary}
        >
          <strong className={styles.summaryHeading}>
            Mainstream vs. competing readings
          </strong>
          <p className={styles.summaryText}>{summary}</p>
        </aside>
      ) : null}

      {selectedReadings.length > 0 ? (
        <aside className={styles.comparisonWorkspace}>
          <div className={styles.comparisonHeader}>
            <h4 className={styles.comparisonHeading}>Comparison workspace</h4>
            <button type="button" onClick={clearComparison}>
              Clear selection
            </button>
          </div>
          {selectedReadings.length < MAX_COMPARISON_SELECTIONS ? (
            <p className={styles.comparisonPrompt}>
              Select another witness to complete the side-by-side comparison.
            </p>
          ) : null}
          <div className={styles.comparisonTableWrapper}>
            <table className={styles.comparisonTable}>
              <thead>
                <tr>
                  <th scope="col">
                    Attribute
                  </th>
                  {selectedReadings.map((reading) => (
                    <th
                      key={reading.id}
                      scope="col"
                    >
                      {readingDisplayName(reading)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row.label}>
                    <th scope="row">
                      {row.label}
                    </th>
                    {selectedReadings.map((reading, index) => (
                      <td key={`${reading.id}-${row.label}`}>
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
      <div className={styles.filters}>
        <label className={styles.filterLabel}>
          <input
            type="checkbox"
            checked={showDisputedOnly}
            onChange={(event) => setShowDisputedOnly(event.target.checked)}
          />
          Disputed readings only
        </label>
        <label className={styles.filterLabel}>
          Category
          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
            className={styles.filterSelect}
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
        <p className={styles.loading} role="status">Loading textual variants…</p>
      ) : error ? (
        <p role="alert" className={styles.error}>
          Unable to load textual variants. {error}
        </p>
      ) : readings.length === 0 ? (
        <p className={styles.noResults}>No textual variants available.</p>
      ) : (
        <div className={styles.resultsGrid}>
          {chronology.length > 0 ? (
            <div className={styles.chronologySection}>
              <h4 className={styles.chronologyHeading}>Manuscript chronology</h4>
              <div
                aria-hidden="true"
                className={styles.chronologyTimeline}
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
                      className={`${styles.chronologyPoint} ${point.disputed ? styles["chronologyPoint--disputed"] : styles["chronologyPoint--mainstream"]}`}
                      style={{
                        left: `calc(${ratio * 100}% - 6px)`,
                      }}
                    />
                  );
                })}
              </div>
              <ul className={styles.chronologyList}>
                {chronology.map((point) => (
                  <li
                    key={`${point.id}-chronology`}
                    className={styles.chronologyItem}
                  >
                    <span>
                      <strong className={styles.chronologyDate}>
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
            <div className={styles.variantsGrid}>
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
                    className={`${styles.variantCard} ${isSelected ? styles["variantCard--selected"] : ""}`}
                  >
                    <header className={styles.variantHeader}>
                      <div className={styles.variantHeaderTop}>
                        <div className={styles.variantInfo}>
                          <div className={styles.variantNameRow}>
                            <strong>{readingDisplayName(reading)}</strong>
                            <span className={styles.variantMeta}>
                              {reading.category}
                              {reading.translation ? ` · ${reading.translation}` : ""}
                            </span>
                          </div>
                          <div className={styles.variantBadges}>
                            {reading.dataset ? (
                              <span className="badge badge-primary text-xs">
                                {reading.dataset}
                              </span>
                            ) : null}
                            {reading.disputed ? (
                              <span className="badge badge-danger text-xs">
                                Disputed
                              </span>
                            ) : null}
                            {confidenceLabel ? (
                              <span className="badge badge-secondary text-xs">
                                {confidenceLabel}
                              </span>
                            ) : null}
                            {reading.witness_metadata?.date ? (
                              <span className="badge badge-warning text-xs">
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
                    <p className={styles.variantReading}>{reading.reading}</p>
                    {reading.note ? (
                      <p className={styles.variantNote}>
                        {reading.note}
                      </p>
                    ) : null}
                    <footer className={styles.variantFooter}>
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
