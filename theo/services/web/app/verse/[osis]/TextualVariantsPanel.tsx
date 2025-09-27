import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "./research-panels";

type ScriptureVerse = {
  osis: string;
  translation: string;
  text: string;
};

type ScriptureResponse = {
  osis: string;
  translation: string;
  verses?: ScriptureVerse[] | null;
};

const TRANSLATIONS: Array<{ code: string; label: string }> = [
  { code: "SBLGNT", label: "SBL Greek NT" },
  { code: "ESV", label: "English Standard Version" },
];

interface TextualVariantsPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

async function fetchTranslation(
  osis: string,
  translation: string,
  baseUrl: string,
): Promise<{ translation: string; verses: ScriptureVerse[]; label: string } | null> {
  const response = await fetch(
    `${baseUrl}/research/scripture?osis=${encodeURIComponent(osis)}&translation=${encodeURIComponent(translation)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error((await response.text()) || response.statusText);
  }
  const payload = (await response.json()) as ScriptureResponse;
  const verses = payload.verses?.filter((verse): verse is ScriptureVerse => Boolean(verse)) ?? [];
  if (verses.length === 0) {
    return null;
  }
  const label = TRANSLATIONS.find((item) => item.code === translation)?.label ?? translation;
  return { translation, verses, label };
}

export default async function TextualVariantsPanel({
  osis,
  features,
}: TextualVariantsPanelProps) {
  if (!features?.textual_variants) {
    return null;
  }

  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  let readings: Array<{ translation: string; verses: ScriptureVerse[]; label: string }> = [];
  let error: string | null = null;

  try {
    const results = await Promise.all(
      TRANSLATIONS.map(async ({ code }) => {
        try {
          return await fetchTranslation(osis, code, baseUrl);
        } catch (translationError) {
          throw translationError;
        }
      }),
    );
    readings = results.filter((result): result is NonNullable<typeof result> => Boolean(result));
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
        <div style={{ display: "grid", gap: "1rem" }}>
          {readings.map((reading) => {
            const combinedText = reading.verses.map((verse) => verse.text).join(" ");
            return (
              <article
                key={reading.translation}
                style={{
                  border: "1px solid var(--border, #e5e7eb)",
                  borderRadius: "0.5rem",
                  padding: "0.75rem",
                  background: "var(--muted, #f8fafc)",
                }}
              >
                <header style={{ marginBottom: "0.5rem" }}>
                  <strong>{reading.label}</strong>
                  <span style={{ marginLeft: "0.5rem", color: "var(--muted-foreground, #4b5563)", fontSize: "0.875rem" }}>
                    {reading.translation}
                  </span>
                </header>
                <p style={{ margin: 0, lineHeight: 1.6 }}>{combinedText}</p>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
