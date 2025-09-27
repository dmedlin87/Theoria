import { formatEmphasisSummary } from "../../mode-config";
import { getActiveMode } from "../../mode-server";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";
import ContradictionsPanelClient from "./ContradictionsPanelClient";

export type ContradictionSnippet = {
  osis: string;
  text: string;
  source_url?: string | null;
};

export type ContradictionSnippetPair = {
  left?: ContradictionSnippet | null;
  right?: ContradictionSnippet | null;
};

export type ContradictionSource = {
  label?: string | null;
  url?: string | null;
};

export type ContradictionRecord = {
  summary: string;
  osis: [string, string];
  severity?: string | null;
  sources?: ContradictionSource[] | null;
  snippet_pairs?: ContradictionSnippetPair[] | null;
};

type ContradictionsResponse = {
  contradictions?: ContradictionRecord[] | null;
};

interface ContradictionsPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default async function ContradictionsPanel({
  osis,
  features,
}: ContradictionsPanelProps) {
  if (!features?.contradictions) {
    return null;
  }

  const mode = getActiveMode();
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  let error: string | null = null;
  let contradictions: ContradictionRecord[] = [];

  try {
    const response = await fetch(
      `${baseUrl}/research/contradictions?osis=${encodeURIComponent(osis)}&mode=${encodeURIComponent(mode.id)}`,
      { cache: "no-store" },
    );
    if (!response.ok) {
      throw new Error((await response.text()) || response.statusText);
    }
    const payload = (await response.json()) as ContradictionsResponse;
    contradictions =
      payload.contradictions?.filter((item): item is ContradictionRecord => Boolean(item)) ?? [];
  } catch (fetchError) {
    console.error("Failed to load contradictions", fetchError);
    error = fetchError instanceof Error ? fetchError.message : "Unknown error";
  }

  return (
    <section
      aria-labelledby="contradictions-heading"
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="contradictions-heading" style={{ marginTop: 0 }}>
        Potential contradictions
      </h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        {formatEmphasisSummary(mode)}
      </p>
      {error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load contradictions. {error}
        </p>
      ) : contradictions.length === 0 ? (
        <p>No contradictions found.</p>
      ) : (
        <ContradictionsPanelClient contradictions={contradictions} />
      )}
    </section>
  );
}
