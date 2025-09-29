"use client";

import { useEffect, useMemo, useState } from "react";

import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "../types";
import ContradictionsPanelClient from "./ContradictionsPanelClient";

export type ContradictionRecord = {
  id: string;
  summary: string;
  osis: [string, string];
  source?: string | null;
  tags?: string[] | null;
  weight?: number | null;
  perspective?: string | null;
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
  perspective?: string | null;
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
    perspective: item.perspective?.trim() ?? null,
  };
}

interface ContradictionsPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default function ContradictionsPanel({ osis, features }: ContradictionsPanelProps) {
  const { mode } = useMode();
  const [error, setError] = useState<string | null>(null);
  const [contradictions, setContradictions] = useState<ContradictionRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedPerspectives, setSelectedPerspectives] = useState<string[]>([
    "skeptical",
    "apologetic",
  ]);
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);

  useEffect(() => {
    if (!features?.contradictions) {
      return;
    }

    let cancelled = false;
    const fetchContradictions = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("osis", osis);
        params.set("mode", mode.id);
        selectedPerspectives.forEach((perspective) => {
          if (perspective) {
            params.append("perspective", perspective);
          }
        });
        const response = await fetch(`${baseUrl}/research/contradictions?${params.toString()}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error((await response.text()) || response.statusText);
        }
        const payload = (await response.json()) as ContradictionsResponse;
        const mapped =
          payload.items
            ?.map((item) => mapContradictionItem(item))
            .filter((item): item is ContradictionRecord => Boolean(item)) ?? [];
        if (!cancelled) {
          setContradictions(mapped);
        }
      } catch (fetchError) {
        console.error("Failed to load contradictions", fetchError);
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : "Unknown error");
          setContradictions([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void fetchContradictions();
    return () => {
      cancelled = true;
    };
  }, [baseUrl, features?.contradictions, mode.id, osis, selectedPerspectives]);

  if (!features?.contradictions) {
    return null;
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
        {modeSummary}
      </p>
      {loading ? (
        <p>Loading contradictions…</p>
      ) : error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load contradictions. {error}
        </p>
      ) : contradictions.length === 0 ? (
        <p>No contradictions found.</p>
      ) : (
        <ContradictionsPanelClient
          contradictions={contradictions}
          selectedPerspectives={selectedPerspectives}
          onPerspectivesChange={setSelectedPerspectives}
        />
      )}
    </section>
  );
}
