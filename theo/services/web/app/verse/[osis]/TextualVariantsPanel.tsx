'use client';

import { useEffect, useMemo, useState } from 'react';

import { useMode, type StudyMode } from '../../context/ModeContext';
import { getApiBaseUrl } from '../../lib/api';
import type { ResearchFeatureFlags } from './research-panels';

type ManuscriptMetadata = {
  name?: string | null;
  siglum?: string | null;
  date?: string | null;
  provenance?: string | null;
};

type VariantReading = {
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
  witness_metadata?: ManuscriptMetadata | null;
};

type VariantApparatusResponse = {
  osis: string;
  readings?: VariantReading[] | null;
  total?: number | null;
};

interface TextualVariantsPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

type ChronologyPoint = {
  id: string;
  label: string;
  year: number;
  dateLabel: string | null;
  disputed: boolean;
};

function parseYear(value?: string | null): number | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  const match = normalized.match(/(-?\d{1,4})/);
  if (!match) {
    return null;
  }
  const raw = parseInt(match[1], 10);
  if (Number.isNaN(raw)) {
    return null;
  }
  if (normalized.includes('bc') || normalized.includes('bce')) {
    return -Math.abs(raw);
  }
  return raw;
}

function formatYearLabel(year: number): string {
  if (year < 0) {
    return `${Math.abs(year)} BCE`;
  }
  if (year === 0) {
    return '1 CE';
  }
  return `${year} CE`;
}

function formatList(items: string[]): string {
  if (items.length === 0) {
    return '';
  }
  if (items.length === 1) {
    return items[0];
  }
  if (items.length === 2) {
    return `${items[0]} and ${items[1]}`;
  }
  const [last, ...restReversed] = items.slice().reverse();
  const rest = restReversed.reverse();
  return `${rest.join(', ')}, and ${last}`;
}

function readingDisplayName(reading: VariantReading): string {
  return (
    reading.witness_metadata?.name ||
    reading.witness ||
    reading.translation ||
    reading.category
  );
}

function buildSummary(readings: VariantReading[], mode: StudyMode): string | null {
  if (readings.length === 0) {
    return null;
  }

  const manuscripts = readings.filter(
    (reading) => reading.category.toLowerCase() === 'manuscript',
  );
  if (manuscripts.length === 0) {
    return null;
  }

  const sorted = manuscripts.slice().sort((a, b) => {
    const aScore = typeof a.confidence === 'number' ? a.confidence : 0;
    const bScore = typeof b.confidence === 'number' ? b.confidence : 0;
    return bScore - aScore;
  });
  const mainstream =
    sorted.find((reading) => reading.disputed !== true) ?? sorted[0];
  if (!mainstream) {
    return null;
  }

  const mainstreamWitnesses = sorted
    .filter(
      (reading) =>
        reading.disputed !== true && reading.reading === mainstream.reading,
    )
    .map(readingDisplayName)
    .filter(Boolean);

  const alternatives = manuscripts
    .filter((reading) => reading.id !== mainstream.id)
    .map((reading) => {
      const label = readingDisplayName(reading);
      const descriptor = label ? `${label} (“${reading.reading}”)` : `“${reading.reading}”`;
      return { descriptor, disputed: reading.disputed === true };
    });

  const alternativeDescriptions = alternatives
    .slice(0, 3)
    .map((entry) => entry.descriptor);

  let summary = '';
  if (mainstreamWitnesses.length > 0) {
    summary += `Mainstream witnesses like ${formatList(mainstreamWitnesses)} support “${mainstream.reading}”.`;
  } else {
    summary += `The strongest manuscript evidence favors “${mainstream.reading}”.`;
  }

  if (alternativeDescriptions.length > 0) {
    const plural = alternativeDescriptions.length > 1;
    summary += ` Competing reading${plural ? 's' : ''} appear in ${formatList(alternativeDescriptions)}.`;
  } else if (manuscripts.length > 1) {
    summary += ' Other manuscripts largely echo this wording.';
  }

  if (mode === 'apologetic') {
    summary += ' From an apologetic perspective this continuity bolsters claims of textual stability.';
  } else if (mode === 'skeptical') {
    summary += ' A skeptical lens treats the alternative readings as prompts for deeper source criticism.';
  }

  return summary;
}

function computeChronology(readings: VariantReading[]): ChronologyPoint[] {
  const points: ChronologyPoint[] = [];
  for (const reading of readings) {
    const dateLabel = reading.witness_metadata?.date ?? null;
    const year = parseYear(dateLabel);
    if (year === null) {
      continue;
    }
    points.push({
      id: reading.id,
      label: readingDisplayName(reading),
      year,
      dateLabel,
      disputed: reading.disputed === true,
    });
  }
  points.sort((a, b) => a.year - b.year);
  return points;
}

export default function TextualVariantsPanel({
  osis,
  features,
}: TextualVariantsPanelProps) {
  const mode = useMode();
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ''), []);
  const [readings, setReadings] = useState<VariantReading[]>([]);
  const [loading, setLoading] = useState<boolean>(Boolean(features?.textual_variants));
  const [error, setError] = useState<string | null>(null);
  const [showDisputedOnly, setShowDisputedOnly] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  useEffect(() => {
    if (!features?.textual_variants) {
      return;
    }

    const controller = new AbortController();

    async function loadVariants() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `${baseUrl}/research/variants?osis=${encodeURIComponent(osis)}`,
          { cache: 'no-store', signal: controller.signal },
        );
        if (!response.ok) {
          throw new Error((await response.text()) || response.statusText);
        }
        const payload = (await response.json()) as VariantApparatusResponse;
        const items = payload.readings?.filter(
          (entry): entry is VariantReading => Boolean(entry),
        );
        setReadings(items ?? []);
      } catch (fetchError) {
        if (fetchError instanceof DOMException && fetchError.name === 'AbortError') {
          return;
        }
        console.error('Failed to load textual variants', fetchError);
        setReadings([]);
        setError(fetchError instanceof Error ? fetchError.message : 'Unknown error');
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadVariants();

    return () => {
      controller.abort();
    };
  }, [baseUrl, osis, features?.textual_variants]);

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
        categoryFilter !== 'all' &&
        reading.category.toLowerCase() !== categoryFilter.toLowerCase()
      ) {
        return false;
      }
      return true;
    });
  }, [readings, showDisputedOnly, categoryFilter]);

  const chronology = useMemo(
    () => computeChronology(readings.filter((reading) => reading.category.toLowerCase() === 'manuscript')),
    [readings],
  );

  const summary = useMemo(() => buildSummary(readings, mode), [readings, mode]);

  if (!features?.textual_variants) {
    return null;
  }

  const minYear = chronology.length > 0 ? chronology[0].year : null;
  const maxYear = chronology.length > 0 ? chronology[chronology.length - 1].year : null;
  const span = minYear !== null && maxYear !== null ? Math.max(maxYear - minYear, 1) : 1;

  return (
    <section
      aria-labelledby="textual-variants-heading"
      style={{
        background: '#fff',
        borderRadius: '0.5rem',
        padding: '1rem',
        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.08)',
      }}
    >
      <h3 id="textual-variants-heading" style={{ marginTop: 0 }}>
        Textual variants
      </h3>
      <p style={{ margin: '0 0 1rem', color: 'var(--muted-foreground, #4b5563)' }}>
        Compare witness readings for <strong>{osis}</strong> with timeline and commentary cues.
      </p>

      {loading ? (
        <p>Loading textual variants…</p>
      ) : error ? (
        <p role="alert" style={{ color: 'var(--danger, #b91c1c)' }}>
          Unable to load textual variants. {error}
        </p>
      ) : readings.length === 0 ? (
        <p>No textual variants available.</p>
      ) : (
        <div style={{ display: 'grid', gap: '1.25rem' }}>
          {summary ? (
            <aside
              aria-label="Variant summary"
              style={{
                background: 'var(--muted, #f8fafc)',
                borderRadius: '0.5rem',
                padding: '0.75rem',
                border: '1px solid var(--border, #e5e7eb)',
              }}
            >
              <strong style={{ display: 'block', marginBottom: '0.25rem' }}>
                Mainstream vs. competing readings
              </strong>
              <p style={{ margin: 0, lineHeight: 1.6 }}>{summary}</p>
            </aside>
          ) : null}

          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0.75rem',
              alignItems: 'center',
            }}
          >
            <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={showDisputedOnly}
                onChange={(event) => setShowDisputedOnly(event.target.checked)}
              />
              Disputed readings only
            </label>
            <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              Category
              <select
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value)}
                style={{ padding: '0.25rem 0.5rem' }}
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

          {chronology.length > 0 ? (
            <div>
              <h4 style={{ margin: '0 0 0.5rem' }}>Manuscript chronology</h4>
              <div
                aria-hidden="true"
                style={{
                  position: 'relative',
                  height: '2px',
                  background: '#e2e8f0',
                  borderRadius: '999px',
                  marginBottom: '0.75rem',
                }}
              >
                {chronology.map((point) => {
                  const ratio =
                    minYear !== null
                      ? Math.min(
                          Math.max((point.year - minYear) / span, 0),
                          1,
                        )
                      : 0.5;
                  return (
                    <span
                      key={point.id}
                      title={`${point.label}${point.dateLabel ? ` · ${point.dateLabel}` : ''}`}
                      style={{
                        position: 'absolute',
                        left: `calc(${ratio * 100}% - 6px)`,
                        top: '-5px',
                        width: '12px',
                        height: '12px',
                        borderRadius: '999px',
                        background: point.disputed ? '#b91c1c' : '#2563eb',
                        border: '2px solid #fff',
                        boxShadow: '0 0 0 1px rgba(15, 23, 42, 0.1)',
                      }}
                    />
                  );
                })}
              </div>
              <ul
                style={{
                  listStyle: 'none',
                  padding: 0,
                  margin: 0,
                  display: 'grid',
                  gap: '0.5rem',
                }}
              >
                {chronology.map((point) => (
                  <li
                    key={`${point.id}-chronology`}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: '1rem',
                      fontSize: '0.875rem',
                      color: 'var(--muted-foreground, #4b5563)',
                    }}
                  >
                    <span>
                      <strong style={{ color: '#1f2937' }}>
                        {point.dateLabel ?? formatYearLabel(point.year)}
                      </strong>
                      {point.disputed ? ' · disputed' : ''}
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
            <div style={{ display: 'grid', gap: '1rem' }}>
              {filteredReadings.map((reading) => {
                const confidenceLabel =
                  typeof reading.confidence === 'number'
                    ? `${Math.round(reading.confidence * 100)}% confidence`
                    : null;
                return (
                  <article
                    key={reading.id}
                    style={{
                      border: '1px solid var(--border, #e5e7eb)',
                      borderRadius: '0.75rem',
                      padding: '0.75rem',
                      background: 'var(--muted, #f8fafc)',
                    }}
                  >
                    <header style={{ marginBottom: '0.5rem' }}>
                      <div
                        style={{
                          display: 'flex',
                          gap: '0.5rem',
                          alignItems: 'baseline',
                          flexWrap: 'wrap',
                        }}
                      >
                        <strong>{readingDisplayName(reading)}</strong>
                        <span
                          style={{
                            fontSize: '0.875rem',
                            color: 'var(--muted-foreground, #4b5563)',
                          }}
                        >
                          {reading.category}
                          {reading.translation ? ` · ${reading.translation}` : ''}
                        </span>
                      </div>
                      <div style={{ marginTop: '0.25rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        {reading.disputed ? (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                              background: '#fee2e2',
                              color: '#991b1b',
                              fontSize: '0.75rem',
                              padding: '0.125rem 0.5rem',
                              borderRadius: '999px',
                            }}
                          >
                            Disputed
                          </span>
                        ) : null}
                        {confidenceLabel ? (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                              background: '#dbeafe',
                              color: '#1d4ed8',
                              fontSize: '0.75rem',
                              padding: '0.125rem 0.5rem',
                              borderRadius: '999px',
                            }}
                          >
                            {confidenceLabel}
                          </span>
                        ) : null}
                        {reading.witness_metadata?.date ? (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                              background: '#ede9fe',
                              color: '#5b21b6',
                              fontSize: '0.75rem',
                              padding: '0.125rem 0.5rem',
                              borderRadius: '999px',
                            }}
                          >
                            {reading.witness_metadata.date}
                          </span>
                        ) : null}
                      </div>
                    </header>
                    <p style={{ margin: '0 0 0.5rem', lineHeight: 1.6 }}>
                      {reading.reading}
                    </p>
                    {reading.note ? (
                      <p
                        style={{
                          margin: 0,
                          fontSize: '0.875rem',
                          color: 'var(--muted-foreground, #4b5563)',
                          lineHeight: 1.6,
                        }}
                      >
                        {reading.note}
                      </p>
                    ) : null}
                    <footer
                      style={{
                        marginTop: '0.75rem',
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '0.75rem',
                        fontSize: '0.875rem',
                        color: 'var(--muted-foreground, #4b5563)',
                      }}
                    >
                      {reading.source ? <span>Source: {reading.source}</span> : null}
                      {reading.witness_metadata?.provenance ? (
                        <span>Provenance: {reading.witness_metadata.provenance}</span>
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

