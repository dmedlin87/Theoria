import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";
import { VariantCompareTable, type VariantReading } from "./VariantCompareTable";

interface TextualVariantsPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

type VariantResponse = {
  osis: string;
  readings?: VariantReading[] | null;
};

export default async function TextualVariantsPanel({
  osis,
  features,
}: TextualVariantsPanelProps) {
  if (!features?.textual_variants) {
    return null;
  }

  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  let readings: VariantReading[] = [];
  let error: string | null = null;

  try {
    const response = await fetch(
      `${baseUrl}/research/variants?osis=${encodeURIComponent(osis)}`,
      { cache: "no-store" },
    );
    if (!response.ok) {
      throw new Error((await response.text()) || response.statusText);
    }
    const payload = (await response.json()) as VariantResponse;
    readings = (payload.readings ?? []).map((reading) => ({
      ...reading,
      note: reading.note ?? null,
      source: reading.source ?? null,
      witness: reading.witness ?? null,
      translation: reading.translation ?? null,
      confidence:
        typeof reading.confidence === "number" ? reading.confidence : null,
    }));
  } catch (fetchError) {
    console.error("Failed to load textual variants", fetchError);
    error = fetchError instanceof Error ? fetchError.message : "Unknown error";
  }

  return (
    <section
      aria-labelledby="textual-variants-heading"
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="textual-variants-heading" style={{ marginTop: 0 }}>
        Textual variants
      </h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        Compare witness readings for <strong>{osis}</strong>.
      </p>
      {error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load textual variants. {error}
        </p>
      ) : readings.length === 0 ? (
        <p>No textual variants available.</p>
      ) : (
        <VariantCompareTable readings={readings} />
      )}
    </section>
  );
}
