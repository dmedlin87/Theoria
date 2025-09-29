import ModeChangeBanner from "../../components/ModeChangeBanner";
import { formatEmphasisSummary } from "../../mode-config";
import { getActiveMode } from "../../mode-server";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";
import CommentariesPanelClient from "./CommentariesPanelClient";

export type CommentaryRecord = {
  id: string;
  osis: string;
  title?: string | null;
  excerpt: string;
  source?: string | null;
  citation?: string | null;
  tags?: string[] | null;
  perspective?: string | null;
};

type CommentaryResponse = {
  osis?: string[] | null;
  items?: CommentaryApiItem[] | null;
};

type CommentaryApiItem = {
  id?: string | null;
  osis?: string | null;
  title?: string | null;
  excerpt?: string | null;
  source?: string | null;
  citation?: string | null;
  tags?: string[] | null;
  perspective?: string | null;
};

function mapCommentaryItem(item: CommentaryApiItem): CommentaryRecord | null {
  const id = item.id?.toString();
  const osis = item.osis?.trim();
  const excerpt = item.excerpt?.trim();
  if (!id || !osis || !excerpt) {
    return null;
  }

  return {
    id,
    osis,
    excerpt,
    title: item.title?.trim() ?? null,
    source: item.source?.trim() ?? null,
    citation: item.citation?.trim() ?? null,
    tags: item.tags ?? null,
    perspective: item.perspective?.trim().toLowerCase() ?? null,
  };
}

interface CommentariesPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default async function CommentariesPanel({ osis, features }: CommentariesPanelProps) {
  if (!features?.commentaries) {
    return null;
  }

  const mode = getActiveMode();
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  let error: string | null = null;
  let commentaries: CommentaryRecord[] = [];

  try {
    const params = new URLSearchParams();
    params.append("osis", osis);
    params.append("mode", mode.id);
    params.append("perspective", "skeptical");
    params.append("perspective", "apologetic");
    const response = await fetch(`${baseUrl}/research/commentaries?${params.toString()}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error((await response.text()) || response.statusText);
    }
    const payload = (await response.json()) as CommentaryResponse;
    commentaries =
      payload.items
        ?.map((item) => mapCommentaryItem(item))
        .filter((item): item is CommentaryRecord => Boolean(item)) ?? [];
  } catch (fetchError) {
    console.error("Failed to load commentaries", fetchError);
    error = fetchError instanceof Error ? fetchError.message : "Unknown error";
  }

  return (
    <section
      aria-labelledby="commentaries-heading"
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="commentaries-heading" style={{ marginTop: 0 }}>
        Commentaries & notes
      </h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        Curated research notes anchored to <strong>{osis}</strong>.
      </p>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #64748b)", fontSize: "0.9rem" }}>
        {formatEmphasisSummary(mode)}
      </p>
      <ModeChangeBanner area="Commentaries" />
      {error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load commentaries. {error}
        </p>
      ) : (
        <CommentariesPanelClient commentaries={commentaries} />
      )}
    </section>
  );
}
