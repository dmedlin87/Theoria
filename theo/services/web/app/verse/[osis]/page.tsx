import dynamic from "next/dynamic";
import Link from "next/link";
import { Suspense } from "react";
import Breadcrumbs from "../../components/Breadcrumbs";
import VirtualList from "../../components/VirtualList";

import DeliverableExportAction, {
  type DeliverableRequestPayload,
} from "../../components/DeliverableExportAction";
import { buildPassageLink, formatAnchor, getApiBaseUrl } from "../../lib/api";
import ResearchPanels from "../../research/ResearchPanels";
import { fetchResearchFeatures } from "../../research/features";
import type { ResearchFeatureFlags } from "../../research/types";
import ReliabilityOverviewCard from "./ReliabilityOverviewCard";
import type { VerseGraphResponse } from "./graphTypes";
import { VerseReliabilitySkeleton, VerseResearchSkeleton } from "./VerseSkeletons";

const VerseGraphSection = dynamic(() => import("./VerseGraphSection"), {
  loading: () => <GraphSectionSkeleton />,
  ssr: false,
});

const TIMELINE_WINDOWS = ["week", "month", "quarter", "year"] as const;
type TimelineWindow = (typeof TIMELINE_WINDOWS)[number];

function GraphSectionSkeleton(): JSX.Element {
  return (
    <div className="card graph-section-skeleton" aria-busy="true">
      <div className="skeleton graph-section-skeleton__title" />
      <div className="skeleton graph-section-skeleton__subtitle" />
      <div className="skeleton graph-section-skeleton__canvas" />
    </div>
  );
}

interface VersePageProps {
  params: { osis: string };
  searchParams?: Record<string, string | string[] | undefined>;
}

interface VerseMention {
  context_snippet: string;
  passage: {
    id: string;
    document_id: string;
    text: string;
    osis_ref?: string | null;
    page_no?: number | null;
    t_start?: number | null;
    t_end?: number | null;
    meta?: Record<string, unknown> | null;
  };
}

interface VerseMentionsResponse {
  osis: string;
  mentions: VerseMention[];
  total: number;
}

interface VerseTimelineBucket {
  label: string;
  start: string;
  end: string;
  count: number;
  document_ids: string[];
  sample_passage_ids: string[];
}

interface VerseTimelineResponse {
  osis: string;
  window: TimelineWindow;
  buckets: VerseTimelineBucket[];
  total_mentions: number;
}

async function fetchGraph(
  osis: string,
  searchParams: VersePageProps["searchParams"],
): Promise<VerseGraphResponse> {
  try {
    const params = buildMentionFilterQuery(searchParams);
    const query = params.toString();
    const baseUrl = getApiBaseUrl().replace(/\/$/, "");
    const response = await fetch(
      `${baseUrl}/verses/${encodeURIComponent(osis)}/graph${
        query ? `?${query}` : ""
      }`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(`Unable to load graph: ${response.statusText}`);
    }

    return (await response.json()) as VerseGraphResponse;
  } catch (error) {
    console.error("Failed to load verse graph", error);
    throw error;
  }
}

function getParamValue(
  searchParams: VersePageProps["searchParams"],
  key: string,
): string | undefined {
  if (!searchParams) {
    return undefined;
  }
  const value = searchParams[key];
  return typeof value === "string" ? value : undefined;
}

function getTimelineWindow(searchParams: VersePageProps["searchParams"]): TimelineWindow {
  const candidate = getParamValue(searchParams, "window");
  if (candidate && TIMELINE_WINDOWS.includes(candidate as TimelineWindow)) {
    return candidate as TimelineWindow;
  }
  return "month";
}

function buildMentionFilterQuery(searchParams: VersePageProps["searchParams"]) {
  const params = new URLSearchParams();
  if (!searchParams) {
    return params;
  }
  const sourceType = getParamValue(searchParams, "source_type");
  const collection = getParamValue(searchParams, "collection");
  const author = getParamValue(searchParams, "author");

  if (sourceType) {
    params.set("source_type", sourceType);
  }
  if (collection) {
    params.set("collection", collection);
  }
  if (author) {
    params.set("author", author);
  }
  return params;
}

async function fetchMentions(
  osis: string,
  searchParams: VersePageProps["searchParams"],
): Promise<VerseMentionsResponse> {
  try {
    const params = buildMentionFilterQuery(searchParams);
    const query = params.toString();
    const baseUrl = getApiBaseUrl().replace(/\/$/, "");
    const response = await fetch(
      `${baseUrl}/verses/${encodeURIComponent(osis)}/mentions${query ? `?${query}` : ""}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(`Unable to load mentions: ${response.statusText}`);
    }

    return (await response.json()) as VerseMentionsResponse;
  } catch (error) {
    console.error("Failed to load verse mentions", error);
    throw error;
  }
}

async function fetchTimeline(
  osis: string,
  searchParams: VersePageProps["searchParams"],
  window: TimelineWindow,
): Promise<VerseTimelineResponse | null> {
  try {
    const params = buildMentionFilterQuery(searchParams);
    params.set("window", window);
    const query = params.toString();
    const baseUrl = getApiBaseUrl().replace(/\/$/, "");
    const response = await fetch(
      `${baseUrl}/verses/${encodeURIComponent(osis)}/timeline${query ? `?${query}` : ""}`,
      {
        cache: "no-store",
      },
    );

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      throw new Error(`Unable to load timeline: ${response.statusText}`);
    }

    return (await response.json()) as VerseTimelineResponse;
  } catch (error) {
    console.error("Failed to load verse timeline", error);
    throw error;
  }
}

const STUDY_MODES = ["apologetic", "skeptical"] as const;
type StudyMode = (typeof STUDY_MODES)[number];

function getActiveMode(searchParams: VersePageProps["searchParams"]): StudyMode {
  const candidate = getParamValue(searchParams, "mode")?.toLowerCase();
  return (STUDY_MODES.find((mode) => mode === candidate) ?? "apologetic") as StudyMode;
}

function isPromise<T>(value: unknown): value is Promise<T> {
  return Boolean(
    value && typeof value === "object" && typeof (value as Promise<T>).then === "function",
  );
}

async function resolveMaybePromise<T>(value: T | Promise<T>): Promise<T> {
  if (isPromise<T>(value)) {
    return value;
  }
  return value as T;
}

function TimelineSection({
  timeline,
  window: activeWindow,
  error,
}: {
  timeline: VerseTimelineResponse | null;
  window: TimelineWindow;
  error: string | null;
}) {
  if (error) {
    return (
      <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
        Unable to load timeline. {error}
      </p>
    );
  }

  if (!timeline) {
    return null;
  }

  if (timeline.buckets.length === 0) {
    return (
      <div className="mt-3">
        <h3 className="mb-2">Timeline</h3>
        <p className="text-muted">
          No mentions found for the selected {activeWindow} window.
        </p>
      </div>
    );
  }

  const maxCount = timeline.buckets.reduce((max, bucket) => Math.max(max, bucket.count), 0) || 1;

  return (
    <div className="mt-3">
      <h3 className="mb-2">Timeline</h3>
      <p className="text-muted mb-3">
        Showing {timeline.buckets.length} {activeWindow} buckets totaling {timeline.total_mentions} mentions.
      </p>
      <ul className="stack-md" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {timeline.buckets.map((bucket) => {
          const ratio = Math.max(bucket.count / maxCount, 0);
          return (
            <li key={`${bucket.label}-${bucket.start}`} className="panel">
              <div className="cluster" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
                <strong>{bucket.label}</strong>
                <span className="text-muted">{bucket.count} mentions</span>
              </div>
              <div
                aria-hidden="true"
                style={{
                  marginTop: "0.5rem",
                  height: "0.5rem",
                  background: "var(--color-border-subtle)",
                  borderRadius: "var(--radius-full)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.round(ratio * 100)}%`,
                    background: "var(--color-accent)",
                    height: "100%",
                  }}
                />
              </div>
              <p className="text-sm text-muted mt-2 mb-0">
                {bucket.document_ids.length} documents · {bucket.sample_passage_ids.length} passages
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default async function VersePage({ params, searchParams }: VersePageProps) {
  const resolvedParams = await resolveMaybePromise(params);
  const normalizedSearchParams = searchParams
    ? await resolveMaybePromise(searchParams)
    : undefined;

  const windowParam = getTimelineWindow(normalizedSearchParams);
  const sourceType = getParamValue(normalizedSearchParams, "source_type") ?? "";
  const collection = getParamValue(normalizedSearchParams, "collection") ?? "";
  const author = getParamValue(normalizedSearchParams, "author") ?? "";
  const activeMode = getActiveMode(normalizedSearchParams);

  let data: VerseMentionsResponse | null = null;
  let error: string | null = null;
  let features: ResearchFeatureFlags = {};
  let timeline: VerseTimelineResponse | null = null;
  let timelineError: string | null = null;
  let graph: VerseGraphResponse | null = null;
  let graphError: string | null = null;
  let featuresError: string | null = null;

  try {
    const [mentionsResponse, featureResult] = await Promise.all([
      fetchMentions(resolvedParams.osis, normalizedSearchParams),
      fetchResearchFeatures(),
    ]);
    data = mentionsResponse;
    features = featureResult.features ?? {};
    featuresError = featureResult.error;
  } catch (err) {
    console.error("Failed to load verse mentions", err);
    error = err instanceof Error ? err.message : "Unknown error";
  }

  try {
    graph = await fetchGraph(resolvedParams.osis, normalizedSearchParams);
  } catch (graphErr) {
    console.error("Failed to load verse graph", graphErr);
    graphError = graphErr instanceof Error ? graphErr.message : "Unknown error";
  }

  if (!error && features.verse_timeline) {
    try {
      timeline = await fetchTimeline(resolvedParams.osis, normalizedSearchParams, windowParam);
    } catch (timelineErr) {
      console.error("Failed to load verse timeline", timelineErr);
      timelineError =
        timelineErr instanceof Error ? timelineErr.message : "Unknown error";
    }
  }

  const osis = data?.osis ?? resolvedParams.osis;
  const mentions = data?.mentions ?? [];
  const total = data?.total ?? 0;
  const deliverableFilters: Record<string, string> = {};
  if (sourceType) {
    deliverableFilters.source_type = sourceType;
  }
  if (collection) {
    deliverableFilters.collection = collection;
  }
  if (author) {
    deliverableFilters.author = author;
  }
  const deliverableRequestPayload: DeliverableRequestPayload = {
    type: "sermon",
    topic: `Sermon prep for ${osis}`,
    osis,
    formats: ["markdown", "ndjson", "pdf"],
  };
  if (Object.keys(deliverableFilters).length > 0) {
    deliverableRequestPayload.filters = deliverableFilters;
  }

  return (
    <section>
      <div className={features.research ? "sidebar-layout" : ""}>
        <div>
          <Breadcrumbs
            items={[
              { label: "Home", href: "/" },
              { label: "Verse mentions" },
              { label: osis },
            ]}
          />
          <h2>Verse Mentions</h2>
          <p>
            Aggregated references for <strong>{osis}</strong>
          </p>

          <Suspense fallback={<VerseReliabilitySkeleton />}>
            <ReliabilityOverviewCard osis={osis} mode={activeMode} />
          </Suspense>

          <DeliverableExportAction
            label="Export sermon packet"
            preparingText="Generating sermon packet…"
            successText="Sermon packet ready."
            idleText="Create a sermon outline with citations."
            requestPayload={deliverableRequestPayload}
          />

          {error ? (
            <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
              Unable to load mentions. {error}
            </p>
          ) : null}

          {graphError ? (
            <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
              Unable to load relationship graph. {graphError}
            </p>
          ) : null}

          {!graphError ? <VerseGraphSection graph={graph} /> : null}

          <form method="get" className="card mt-3">
            <div className="stack-md">
              <div className="form-field">
                <label htmlFor="source_type" className="form-label">
                  Source type
                </label>
                <select id="source_type" name="source_type" defaultValue={sourceType} className="form-select">
                  <option value="">All sources</option>
                  <option value="pdf">PDF</option>
                  <option value="markdown">Markdown</option>
                  <option value="youtube">YouTube</option>
                  <option value="transcript">Transcript</option>
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="collection" className="form-label">
                  Collection
                </label>
                <input
                  id="collection"
                  name="collection"
                  type="text"
                  defaultValue={collection}
                  placeholder="Collection"
                  className="form-input"
                />
              </div>

              <div className="form-field">
                <label htmlFor="author" className="form-label">
                  Author
                </label>
                <input
                  id="author"
                  name="author"
                  type="text"
                  defaultValue={author}
                  placeholder="Author"
                  className="form-input"
                />
              </div>

              <div className="form-field">
                <label htmlFor="window" className="form-label">
                  Window
                </label>
                <select id="window" name="window" defaultValue={windowParam} className="form-select">
                  {TIMELINE_WINDOWS.map((option) => (
                    <option key={option} value={option}>
                      {option.charAt(0).toUpperCase() + option.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              <button type="submit" className="btn btn-primary">
                Apply filters
              </button>
            </div>
          </form>

          <p>
            Showing {mentions.length} of {total} mentions
          </p>

          {featuresError ? (
            <p role="alert" style={{ margin: "0 0 1rem", color: "#b91c1c" }}>
              Unable to load research capabilities. {featuresError}
            </p>
          ) : null}

          {features.verse_timeline ? (
            <TimelineSection timeline={timeline} window={windowParam} error={timelineError} />
          ) : null}

          {mentions.length === 0 ? (
            <div className="alert alert-info">
              <div className="alert__message">No mentions found for the selected filters.</div>
            </div>
          ) : (
            <VirtualList
              items={mentions}
              itemKey={(mention) => mention.passage.id}
              estimateSize={() => 200}
              containerProps={{
                className: "verse-mentions__scroller",
                role: "list",
                "aria-label": "Verse mentions",
              }}
              renderItem={(mention, index) => {
                const anchor = formatAnchor({
                  page_no: mention.passage.page_no ?? null,
                  t_start: mention.passage.t_start ?? null,
                  t_end: mention.passage.t_end ?? null,
                });
                const documentTitle =
                  (mention.passage.meta?.document_title as string | undefined) ?? "Untitled document";
                return (
                  <div
                    role="listitem"
                    className="card verse-mentions__item"
                    data-last={index === mentions.length - 1}
                  >
                    <article className="stack-sm">
                      <header className="stack-xs">
                        <h3 className="text-lg font-semibold mb-0">{documentTitle}</h3>
                        {anchor && <p className="text-sm text-muted mb-0">{anchor}</p>}
                        {mention.passage.osis_ref && <p className="text-sm text-muted mb-0">OSIS: {mention.passage.osis_ref}</p>}
                      </header>
                      <p className="mb-0">{mention.context_snippet}</p>
                      <footer>
                        <Link
                          href={buildPassageLink(mention.passage.document_id, mention.passage.id, {
                            pageNo: mention.passage.page_no ?? null,
                            tStart: mention.passage.t_start ?? null,
                          })}
                          className="btn btn-secondary btn-sm"
                        >
                          Open document
                        </Link>
                      </footer>
                    </article>
                  </div>
                );
              }}
            />
          )}
        </div>
        {features.research ? (
          <aside aria-label="Research panels" className="panel">
            <Suspense fallback={<VerseResearchSkeleton />}>
              <ResearchPanels osis={osis} features={features} />
            </Suspense>
          </aside>
        ) : null}
      </div>
    </section>
  );
}
