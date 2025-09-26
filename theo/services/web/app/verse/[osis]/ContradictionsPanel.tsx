import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";

type ContradictionRecord = {
  summary: string;
  osis: [string, string];
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

  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  let error: string | null = null;
  let contradictions: ContradictionRecord[] = [];

  try {
    const response = await fetch(
      `${baseUrl}/research/contradictions?osis=${encodeURIComponent(osis)}`,
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
      {error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load contradictions. {error}
        </p>
      ) : contradictions.length === 0 ? (
        <p>No contradictions found.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.75rem" }}>
          {contradictions.map((item, index) => (
            <li
              key={`${item.summary}-${index}`}
              style={{
                border: "1px solid var(--border, #e5e7eb)",
                borderRadius: "0.5rem",
                padding: "0.75rem",
              }}
            >
              <p style={{ margin: "0 0 0.5rem" }}>{item.summary}</p>
              <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--muted-foreground, #4b5563)" }}>
                {item.osis[0]} ⇄ {item.osis[1]}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
