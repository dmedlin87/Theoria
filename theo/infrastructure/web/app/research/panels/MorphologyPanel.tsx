"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./MorphologyPanel.module.css";

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
      className={styles.panel}
    >
      <h3 id="morphology-heading" className={styles.panelHeading}>
        Morphology
      </h3>
      <p className={styles.description}>
        Analyze lexical and grammatical details for <strong>{osis}</strong>.
      </p>
      <p className={styles.modeSummary}>
        {modeSummary}
      </p>
      {loading ? (
        <p>Loading morphology…</p>
      ) : error ? (
        <p role="alert" className={styles.errorMessage}>
          Unable to load morphology. {error}
        </p>
      ) : tokens.length === 0 ? (
        <p>No morphology tokens available.</p>
      ) : (
        <div className={styles.tableContainer}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.tableHeader}>
                  Surface
                </th>
                <th className={styles.tableHeader}>
                  Lemma
                </th>
                <th className={styles.tableHeader}>
                  Morphology
                </th>
                <th className={styles.tableHeader}>
                  Gloss
                </th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((token) => (
                <tr key={`${token.osis}-${token.position ?? "0"}`}>
                  <td className={styles.tableCell}>
                    {token.surface}
                  </td>
                  <td className={styles.tableCell}>
                    {token.lemma ?? "—"}
                  </td>
                  <td className={styles.tableCell}>
                    {token.morph ?? "—"}
                  </td>
                  <td className={styles.tableCell}>
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
