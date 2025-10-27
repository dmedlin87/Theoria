"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./CrossReferencesPanel.module.css";

import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "../types";

type CrossReferenceItem = {
  source: string;
  target: string;
  weight?: number | null;
  relation_type?: string | null;
  summary?: string | null;
  dataset?: string | null;
};

type CrossReferenceResponse = {
  osis: string;
  results?: CrossReferenceItem[] | null;
  total?: number | null;
};

interface CrossReferencesPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default function CrossReferencesPanel({ osis, features }: CrossReferencesPanelProps) {
  const { mode } = useMode();
  const [items, setItems] = useState<CrossReferenceItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);

  useEffect(() => {
    if (!features?.cross_references) {
      return;
    }

    let cancelled = false;
    const fetchCrossReferences = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `${baseUrl}/research/crossrefs?osis=${encodeURIComponent(osis)}&mode=${encodeURIComponent(mode.id)}`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          throw new Error((await response.text()) || response.statusText);
        }
        const payload = (await response.json()) as CrossReferenceResponse;
        const mapped = payload.results?.filter((entry): entry is CrossReferenceItem => Boolean(entry)) ?? [];
        if (!cancelled) {
          setItems(mapped);
        }
      } catch (fetchError) {
        console.error("Failed to load cross-references", fetchError);
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : "Unknown error");
          setItems([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void fetchCrossReferences();
    return () => {
      cancelled = true;
    };
  }, [baseUrl, features?.cross_references, mode.id, osis]);

  if (!features?.cross_references) {
    return null;
  }

  return (
    <section
      aria-labelledby="cross-references-heading"
      className={styles.panel}
    >
      <h3 id="cross-references-heading" className={styles.panelHeading}>
        Cross-references
      </h3>
      <p className={styles.description}>
        Connections cited with <strong>{osis}</strong>.
      </p>
      <p className={styles.modeSummary}>
        {modeSummary}
      </p>
      {loading ? (
        <p>Loading cross-references…</p>
      ) : error ? (
        <p role="alert" className={styles.errorMessage}>
          Unable to load cross-references. {error}
        </p>
      ) : items.length === 0 ? (
        <p>No cross-references available.</p>
      ) : (
        <ul className={styles.referencesList}>
          {items.map((item) => (
            <li
              key={`${item.source}-${item.target}-${item.dataset ?? "default"}`}
              className={styles.referenceCard}
            >
              <p className={styles.referenceTarget}>
                <strong>{item.target}</strong>
                {item.summary ? ` — ${item.summary}` : ""}
              </p>
              <p className={styles.referenceMetadata}>
                Source: {item.source}
                {item.relation_type ? ` · ${item.relation_type}` : ""}
                {typeof item.weight === "number" ? ` · Weight ${item.weight.toFixed(2)}` : ""}
                {item.dataset ? ` · ${item.dataset}` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
