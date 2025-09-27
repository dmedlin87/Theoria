import Link from "next/link";
import { Suspense } from "react";

import DeliverableExportAction from "../../components/DeliverableExportAction";
import { buildPassageLink, formatAnchor, getApiBaseUrl } from "../../lib/api";
import ResearchPanels, { type ResearchFeatureFlags } from "./research-panels";

const TIMELINE_WINDOWS = ["week", "month", "quarter", "year"] as const;
type TimelineWindow = (typeof TIMELINE_WINDOWS)[number];

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

async function fetchDiscoveryFeatures(): Promise<ResearchFeatureFlags> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  try {
    const response = await fetch(`${baseUrl}/features/discovery`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const payload = (await response.json()) as unknown;
    if (payload && typeof payload === "object" && "features" in payload) {
      const { features } = payload as { features?: ResearchFeatureFlags | null };
      return features ?? {};
    }
    if (payload && typeof payload === "object") {
      return payload as ResearchFeatureFlags;
    }
    return {};
  } catch (error) {
    console.error("Failed to load discovery features", error);
    return {};
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
}

async function fetchTimeline(
  osis: string,
  searchParams: VersePageProps["searchParams"],
  window: TimelineWindow,
): Promise<VerseTimelineResponse | null> {
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
      <div style={{ margin: "1.5rem 0" }}>
        <h3 style={{ margin: "0 0 0.5rem" }}>Timeline</h3>
        <p style={{ color: "var(--muted-foreground, #4b5563)" }}>
          No mentions found for the selected {activeWindow} window.
        </p>
      </div>
    );
  }

  const maxCount = timeline.buckets.reduce((max, bucket) => Math.max(max, bucket.count), 0) || 1;

  return (
    <div style={{ margin: "1.5rem 0" }}>
      <h3 style={{ margin: "0 0 0.5rem" }}>Timeline</h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        Showing {timeline.buckets.length} {activeWindow} buckets totaling {timeline.total_mentions} mentions.
      </p>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "1rem" }}>
        {timeline.buckets.map((bucket) => {
          const ratio = Math.max(bucket.count / maxCount, 0);
          return (
            <li key={`${bucket.label}-${bucket.start}`} style={{ background: "#f8fafc", padding: "1rem", borderRadius: "0.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "1rem" }}>
                <strong>{bucket.label}</strong>
                <span style={{ color: "var(--muted-foreground, #4b5563)" }}>{bucket.count} mentions</span>
              </div>
              <div
                aria-hidden="true"
                style={{
                  marginTop: "0.5rem",
                  height: "0.5rem",
                  background: "#e2e8f0",
                  borderRadius: "999px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.round(ratio * 100)}%`,
                    background: "#2563eb",
                    height: "100%",
                  }}
                />
              </div>
              <p style={{ margin: "0.5rem 0 0", color: "var(--muted-foreground, #4b5563)", fontSize: "0.875rem" }}>
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
  const windowParam = getTimelineWindow(searchParams);
  const sourceType = getParamValue(searchParams, "source_type") ?? "";
  const collection = getParamValue(searchParams, "collection") ?? "";
  const author = getParamValue(searchParams, "author") ?? "";

  let data: VerseMentionsResponse | null = null;
  let error: string | null = null;
  let features: ResearchFeatureFlags = {};
  let timeline: VerseTimelineResponse | null = null;
  let timelineError: string | null = null;

  try {
    const [mentionsResponse, featureFlags] = await Promise.all([
      fetchMentions(params.osis, searchParams),
      fetchDiscoveryFeatures(),
    ]);
    data = mentionsResponse;
    features = featureFlags;
  } catch (err) {
    console.error("Failed to load verse mentions", err);
    error = err instanceof Error ? err.message : "Unknown error";
  }

  if (!error && features.verse_timeline) {
    try {
      timeline = await fetchTimeline(params.osis, searchParams, windowParam);
    } catch (timelineErr) {
      console.error("Failed to load verse timeline", timelineErr);
      timelineError =
        timelineErr instanceof Error ? timelineErr.message : "Unknown error";
    }
  }

  const osis = data?.osis ?? params.osis;
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

  return (
    <section>
      <div
        style={{
          display: "grid",
          gap: "2rem",
          alignItems: "start",
          gridTemplateColumns: features.research ? "minmax(0, 2fr) minmax(0, 1fr)" : "1fr",
        }}
      >
        <div>
          <h2>Verse Mentions</h2>
          <p>
            Aggregated references for <strong>{osis}</strong>
          </p>

          <DeliverableExportAction
            label="Export sermon packet"
            preparingText="Generating sermon packet…"
            successText="Sermon packet ready."
            idleText="Create a sermon outline with citations."
            requestPayload={{
              type: "sermon",
              topic: `Sermon prep for ${osis}`,
              osis,
              formats: ["markdown", "ndjson"],
              filters:
                Object.keys(deliverableFilters).length > 0
                  ? deliverableFilters
                  : undefined,
            }}
          />

          {error ? (
            <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
              Unable to load mentions. {error}
            </p>
          ) : null}

          <form method="get" style={{ margin: "1rem 0", display: "grid", gap: "0.75rem", maxWidth: 480 }}>
            <label style={{ display: "block" }}>
              Source type
              <select name="source_type" defaultValue={sourceType} style={{ width: "100%" }}>
                <option value="">All sources</option>
                <option value="pdf">PDF</option>
                <option value="markdown">Markdown</option>
                <option value="youtube">YouTube</option>
                <option value="transcript">Transcript</option>
              </select>
            </label>
            <label style={{ display: "block" }}>
              Collection
              <input
                name="collection"
                type="text"
                defaultValue={collection}
                placeholder="Collection"
                style={{ width: "100%" }}
              />
            </label>
            <label style={{ display: "block" }}>
              Author
              <input
                name="author"
                type="text"
                defaultValue={author}
                placeholder="Author"
                style={{ width: "100%" }}
              />
            </label>
            <label style={{ display: "block" }}>
              Window
              <select name="window" defaultValue={windowParam} style={{ width: "100%" }}>
                {TIMELINE_WINDOWS.map((option) => (
                  <option key={option} value={option}>
                    {option.charAt(0).toUpperCase() + option.slice(1)}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" style={{ marginTop: "0.5rem" }}>
              Apply filters
            </button>
          </form>

          <p>
            Showing {mentions.length} of {total} mentions
          </p>

          {features.verse_timeline ? (
            <TimelineSection timeline={timeline} window={windowParam} error={timelineError} />
          ) : null}

          {mentions.length === 0 ? (
            <p>No mentions found for the selected filters.</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: "1rem" }}>
              {mentions.map((mention) => {
                const anchor = formatAnchor({
                  page_no: mention.passage.page_no ?? undefined,
                  t_start: mention.passage.t_start ?? undefined,
                  t_end: mention.passage.t_end ?? undefined,
                });
                const documentTitle =
                  (mention.passage.meta?.document_title as string | undefined) ?? "Untitled document";
                return (
                  <li key={mention.passage.id} style={{ background: "#fff", padding: "1rem", borderRadius: "0.5rem" }}>
                    <article>
                      <header>
                        <h3 style={{ margin: "0 0 0.5rem" }}>{documentTitle}</h3>
                        {anchor && <p style={{ margin: "0 0 0.5rem" }}>{anchor}</p>}
                        {mention.passage.osis_ref && <p style={{ margin: 0 }}>OSIS: {mention.passage.osis_ref}</p>}
                      </header>
                      <p style={{ marginTop: "0.75rem" }}>{mention.context_snippet}</p>
                      <footer style={{ marginTop: "0.75rem" }}>
                        <Link
                          href={buildPassageLink(mention.passage.document_id, mention.passage.id, {
                            pageNo: mention.passage.page_no ?? undefined,
                            tStart: mention.passage.t_start ?? undefined,
                          })}
                        >
                          Open document
                        </Link>
                      </footer>
                    </article>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        {features.research ? (
          <aside
            aria-label="Research panels"
            style={{
              background: "#f8fafc",
              borderRadius: "0.75rem",
              padding: "1.5rem",
              border: "1px solid var(--border, #e5e7eb)",
            }}
          >
            <Suspense fallback={<p>Loading research tools…</p>}>
              <ResearchPanels osis={osis} features={features} />
            </Suspense>
          </aside>
        ) : null}
      </div>
    </section>
  );
}
