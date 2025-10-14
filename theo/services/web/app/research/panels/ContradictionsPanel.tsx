"use client";

import { useEffect, useMemo, useState } from "react";

import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "../types";
import ContradictionsPanelClient, {
  initializeModeState,
  type ModeState,
  type ViewingMode,
} from "./ContradictionsPanelClient";
import styles from "./ContradictionsPanel.module.css";

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
    perspective: item.perspective?.trim().toLowerCase() ?? null,
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
  const [viewingMode, setViewingMode] = useState<ViewingMode>("neutral");
  const [modeState, setModeState] = useState<ModeState>(() => initializeModeState());
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);
  const activePerspectives = useMemo(() => {
    const perspectives: string[] = [];
    if (modeState.skeptical) {
      perspectives.push("skeptical");
    }
    if (modeState.apologetic) {
      perspectives.push("apologetic");
    }
    if (modeState.neutral) {
      perspectives.push("neutral");
    }
    return perspectives;
  }, [modeState]);

  useEffect(() => {
    setModeState(() => {
      switch (viewingMode) {
        case "skeptical":
          return { neutral: true, skeptical: true, apologetic: false };
        case "apologetic":
          return { neutral: true, skeptical: false, apologetic: true };
        default:
          return { neutral: true, skeptical: true, apologetic: true };
      }
    });
  }, [viewingMode]);

  useEffect(() => {
    if (!features?.contradictions) {
      return;
    }

    if (activePerspectives.length === 0) {
      setContradictions([]);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    const fetchContradictions = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.append("osis", osis);
        params.append("mode", mode.id);
        activePerspectives.forEach((perspective) => params.append("perspective", perspective));
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
  }, [
    activePerspectives,
    baseUrl,
    features?.contradictions,
    mode.id,
    osis,
  ]);

  if (!features?.contradictions) {
    return null;
  }

  return (
    <section
      aria-labelledby="contradictions-heading"
      className={styles.container}
    >
      <h3 id="contradictions-heading" className={styles.heading}>
        Potential contradictions
      </h3>
      <p className={styles.description}>
        {modeSummary}
      </p>
      {loading ? (
        <p>Loading contradictions…</p>
      ) : error ? (
        <p role="alert" className={styles.errorMessage}>
          Unable to load contradictions. {error}
        </p>
      ) : contradictions.length === 0 ? (
        <p>No contradictions found.</p>
      ) : (
        <ContradictionsPanelClient
          contradictions={contradictions}
          viewingMode={viewingMode}
          onViewingModeChange={setViewingMode}
          modeState={modeState}
          onModeStateChange={setModeState}
        />
      )}
    </section>
  );
}
