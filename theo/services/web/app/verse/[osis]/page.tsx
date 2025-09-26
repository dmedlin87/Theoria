import Link from "next/link";
import { Suspense } from "react";

import { buildPassageLink, formatAnchor, getApiBaseUrl } from "../../lib/api";
import ResearchPanels, { type ResearchFeatureFlags } from "./research-panels";

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

function buildFilterQuery(searchParams: VersePageProps["searchParams"]) {
  const params = new URLSearchParams();
  if (!searchParams) {
    return params;
  }
  const { source_type, collection, author } = searchParams;
  if (typeof source_type === "string" && source_type) {
    params.set("source_type", source_type);
  }
  if (typeof collection === "string" && collection) {
    params.set("collection", collection);
  }
  if (typeof author === "string" && author) {
    params.set("author", author);
  }
  return params;
}

async function fetchMentions(
  osis: string,
  searchParams: VersePageProps["searchParams"],
): Promise<VerseMentionsResponse> {
  const params = buildFilterQuery(searchParams);
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

export default async function VersePage({ params, searchParams }: VersePageProps) {
  const currentFilters = buildFilterQuery(searchParams);

  let data: VerseMentionsResponse | null = null;
  let error: string | null = null;
  let features: ResearchFeatureFlags = {};

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

  const osis = data?.osis ?? params.osis;
  const mentions = data?.mentions ?? [];
  const total = data?.total ?? 0;

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

          {error ? (
            <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
              Unable to load mentions. {error}
            </p>
          ) : null}

          <form method="get" style={{ margin: "1rem 0", display: "grid", gap: "0.75rem", maxWidth: 480 }}>
            <label style={{ display: "block" }}>
              Source type
              <select name="source_type" defaultValue={currentFilters.get("source_type") ?? ""} style={{ width: "100%" }}>
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
                defaultValue={currentFilters.get("collection") ?? ""}
                placeholder="Collection"
                style={{ width: "100%" }}
              />
            </label>
            <label style={{ display: "block" }}>
              Author
              <input
                name="author"
                type="text"
                defaultValue={currentFilters.get("author") ?? ""}
                placeholder="Author"
                style={{ width: "100%" }}
              />
            </label>
            <button type="submit" style={{ marginTop: "0.5rem" }}>
              Apply filters
            </button>
          </form>

          <p>
            Showing {mentions.length} of {total} mentions
          </p>

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
