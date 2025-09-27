import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";

type MorphToken = {
  osis: string;
  surface: string;
  lemma?: string | null;
  morph?: string | null;
  gloss?: string | null;
  position?: number | null;
};

type MorphologyResponse = {
  osis: string;
  tokens?: MorphToken[] | null;
};

interface MorphologyPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default async function MorphologyPanel({
  osis,
  features,
}: MorphologyPanelProps) {
  if (!features?.morphology) {
    return null;
  }

  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  let tokens: MorphToken[] = [];
  let error: string | null = null;

  try {
    const response = await fetch(
      `${baseUrl}/research/morphology?osis=${encodeURIComponent(osis)}`,
      { cache: "no-store" },
    );
    if (!response.ok) {
      throw new Error((await response.text()) || response.statusText);
    }
    const payload = (await response.json()) as MorphologyResponse;
    tokens = payload.tokens?.filter((item): item is MorphToken => Boolean(item)) ?? [];
  } catch (fetchError) {
    console.error("Failed to load morphology", fetchError);
    error = fetchError instanceof Error ? fetchError.message : "Unknown error";
  }

  return (
    <section
      aria-labelledby="morphology-heading"
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="morphology-heading" style={{ marginTop: 0 }}>
        Morphology
      </h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        Analyze lexical and grammatical details for <strong>{osis}</strong>.
      </p>
      {error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load morphology. {error}
        </p>
      ) : tokens.length === 0 ? (
        <p>No morphology tokens available.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border, #e5e7eb)" }}>
                  Surface
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border, #e5e7eb)" }}>
                  Lemma
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border, #e5e7eb)" }}>
                  Morphology
                </th>
                <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid var(--border, #e5e7eb)" }}>
                  Gloss
                </th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((token) => (
                <tr key={`${token.osis}-${token.position ?? "0"}`}>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border, #e5e7eb)" }}>
                    {token.surface}
                  </td>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border, #e5e7eb)" }}>
                    {token.lemma ?? "—"}
                  </td>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border, #e5e7eb)" }}>
                    {token.morph ?? "—"}
                  </td>
                  <td style={{ padding: "0.5rem", borderBottom: "1px solid var(--border, #e5e7eb)" }}>
                    {token.gloss ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
