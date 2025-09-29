"use client";

import { useEffect, useMemo, useState } from "react";

import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "../types";

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

export default function MorphologyPanel({ osis, features }: MorphologyPanelProps) {
  const { mode } = useMode();
  const [tokens, setTokens] = useState<MorphToken[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);

  useEffect(() => {
    if (!features?.morphology) {
      return;
    }

    let cancelled = false;
    const fetchMorphology = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `${baseUrl}/research/morphology?osis=${encodeURIComponent(osis)}&mode=${encodeURIComponent(mode.id)}`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          throw new Error((await response.text()) || response.statusText);
        }
        const payload = (await response.json()) as MorphologyResponse;
        const mapped = payload.tokens?.filter((item): item is MorphToken => Boolean(item)) ?? [];
        if (!cancelled) {
          setTokens(mapped);
        }
      } catch (fetchError) {
        console.error("Failed to load morphology", fetchError);
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : "Unknown error");
          setTokens([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void fetchMorphology();
    return () => {
      cancelled = true;
    };
  }, [baseUrl, features?.morphology, mode.id, osis]);

  if (!features?.morphology) {
    return null;
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
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #64748b)", fontSize: "0.875rem" }}>
        {modeSummary}
      </p>
      {loading ? (
        <p>Loading morphology…</p>
      ) : error ? (
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
