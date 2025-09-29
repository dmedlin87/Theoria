"use client";

import { useEffect, useMemo, useState } from "react";

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
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="cross-references-heading" style={{ marginTop: 0 }}>
        Cross-references
      </h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        Connections cited with <strong>{osis}</strong>.
      </p>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #64748b)", fontSize: "0.875rem" }}>
        {modeSummary}
      </p>
      {loading ? (
        <p>Loading cross-references…</p>
      ) : error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load cross-references. {error}
        </p>
      ) : items.length === 0 ? (
        <p>No cross-references available.</p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "grid",
            gap: "0.75rem",
          }}
        >
          {items.map((item) => (
            <li
              key={`${item.source}-${item.target}-${item.dataset ?? "default"}`}
              style={{
                border: "1px solid var(--border, #e5e7eb)",
                borderRadius: "0.5rem",
                padding: "0.75rem",
              }}
            >
              <p style={{ margin: "0 0 0.25rem" }}>
                <strong>{item.target}</strong>
                {item.summary ? ` — ${item.summary}` : ""}
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: "0.875rem",
                  color: "var(--muted-foreground, #4b5563)",
                }}
              >
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
