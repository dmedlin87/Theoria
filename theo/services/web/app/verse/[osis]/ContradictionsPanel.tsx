import { formatEmphasisSummary } from "../../mode-config";
import { getActiveMode } from "../../mode-server";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";
import ContradictionsPanelClient from "./ContradictionsPanelClient";

export type ContradictionRecord = {
  id: string;
  summary: string;
  osis: [string, string];
  source?: string | null;
  tags?: string[] | null;
  weight?: number | null;
};

type ContradictionsResponse = {
  items?: ContradictionsApiItem[] | null;
};

type ContradictionsApiItem = {
  id?: string | null;
  osis_a?: string | null;
  osis_b?: string | null;
  summary?: string | null;
  source?: string | null;
  tags?: string[] | null;
  weight?: number | string | null;
};

function mapContradictionItem(item: ContradictionsApiItem): ContradictionRecord | null {
  const osisA = item.osis_a?.trim();
  const osisB = item.osis_b?.trim();
  const summary = item.summary?.trim();

  if (!osisA || !osisB || !summary) {
    return null;
  }

  let weight: number | null = null;
  if (item.weight != null) {
    if (typeof item.weight === "number") {
      weight = Number.isFinite(item.weight) ? item.weight : null;
    } else {
      const parsed = Number(item.weight);
      weight = Number.isFinite(parsed) ? parsed : null;
    }
  }

  return {
    id: item.id?.toString() ?? `${osisA}:${osisB}:${summary}`,
    summary,
    osis: [osisA, osisB],
    source: item.source?.trim() ?? null,
    tags: item.tags ?? null,
    weight,
  };
}

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
      payload.items
        ?.map((item) => mapContradictionItem(item))
        .filter((item): item is ContradictionRecord => Boolean(item)) ?? [];
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
