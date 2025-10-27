"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./CommentariesPanel.module.css";

import ModeChangeBanner from "../../components/ModeChangeBanner";
import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "../types";

type CommentaryExcerpt = {
  id: string;
  osis: string;
  title?: string | null;
  excerpt: string;
  source?: string | null;
  perspective?: string | null;
  tags?: string[] | null;
};

type CommentaryResponse = {
  osis: string;
  items?: CommentaryExcerpt[] | null;
  total?: number | null;
};

type CommentaryPerspective = "skeptical" | "apologetic" | "neutral";

type CommentaryPerspectiveState = Record<CommentaryPerspective, boolean>;

const commentaryPerspectiveOptions: {
  id: CommentaryPerspective;
  label: string;
  description: string;
}[] = [
  {
    id: "skeptical",
    label: "Skeptical",
    description: "critical readings and historical challenges",
  },
  {
    id: "apologetic",
    label: "Apologetic",
    description: "harmonies and confessional defences",
  },
  {
    id: "neutral",
    label: "Neutral",
    description: "lexical or background notes",
  },
];

interface CommentariesPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default function CommentariesPanel({ osis, features }: CommentariesPanelProps) {
  const { mode } = useMode();
  const [commentaries, setCommentaries] = useState<CommentaryExcerpt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [perspectiveState, setPerspectiveState] = useState<CommentaryPerspectiveState>(() => ({
    skeptical: true,
    apologetic: true,
    neutral: true,
  }));
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);
  const activePerspectives = useMemo(() => {
    const perspectives: CommentaryPerspective[] = [];
    if (perspectiveState.skeptical) {
      perspectives.push("skeptical");
    }
    if (perspectiveState.apologetic) {
      perspectives.push("apologetic");
    }
    if (perspectiveState.neutral) {
      perspectives.push("neutral");
    }
    return perspectives;
  }, [perspectiveState]);

  useEffect(() => {
    if (!features?.commentaries) {
      return;
    }

    if (activePerspectives.length === 0) {
      setCommentaries([]);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    const fetchNotes = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.append("osis", osis);
        params.append("mode", mode.id);
        activePerspectives.forEach((perspective) => params.append("perspective", perspective));
        const response = await fetch(`${baseUrl}/research/commentaries?${params.toString()}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error((await response.text()) || response.statusText);
        }
        const payload = (await response.json()) as CommentaryResponse;
        const mapped =
          payload.items?.filter((item): item is CommentaryExcerpt => Boolean(item?.excerpt && item?.id)) ?? [];
        if (!cancelled) {
          setCommentaries(mapped);
        }
      } catch (fetchError) {
        console.error("Failed to load commentaries", fetchError);
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : "Unknown error");
          setCommentaries([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void fetchNotes();
    return () => {
      cancelled = true;
    };
  }, [
    activePerspectives,
    baseUrl,
    features?.commentaries,
    mode.id,
    osis,
  ]);

  if (!features?.commentaries) {
    return null;
  }

  return (
    <section
      aria-labelledby="commentaries-heading"
      className={styles.panel}
    >
      <h3 id="commentaries-heading" className={styles.panelHeading}>
        Commentaries & notes
      </h3>
      <p className={styles.description}>
        Curated research notes anchored to <strong>{osis}</strong>.
      </p>
      <p className={styles.modeSummary}>
        {modeSummary}
      </p>
      <div className={styles.filterContainer}>
        <fieldset className={styles.fieldset}>
          <legend className={styles.legend}>Perspectives</legend>
          {commentaryPerspectiveOptions.map((option) => (
            <label
              key={option.id}
              className={styles.checkboxLabel}
            >
              <input
                type="checkbox"
                checked={perspectiveState[option.id]}
                onChange={(event) =>
                  setPerspectiveState((prev) => ({
                    ...prev,
                    [option.id]: event.target.checked,
                  }))
                }
              />
              <span>
                <strong>{option.label}</strong>
                <span className={styles.optionDescription}>
                  {option.description}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
        <ModeChangeBanner area="Commentaries" />
      </div>
      {activePerspectives.length === 0 ? (
        <p className={styles.emptyMessage}>
          All perspectives are hidden. Enable at least one checkbox to surface commentary excerpts.
        </p>
      ) : loading ? (
        <p>Loading commentaries…</p>
      ) : error ? (
        <p role="alert" className={styles.errorMessage}>
          Unable to load commentaries. {error}
        </p>
      ) : commentaries.length === 0 ? (
        <p>No commentaries recorded yet.</p>
      ) : (
        <ul className={styles.commentariesList}>
          {commentaries.map((note) => (
            <li
              key={note.id}
              className={styles.commentaryCard}
            >
              <header className={styles.commentaryHeader}>
                <h4 className={styles.commentaryTitle}>{note.title ?? "Untitled commentary"}</h4>
                <div className={styles.metaRow}>
                  <span className={styles.osisLabel}>
                    OSIS: {note.osis}
                  </span>
                  {note.perspective ? (
                    <span
                      className={`${styles.perspectiveBadge} ${styles[note.perspective]}`}
                    >
                      {note.perspective}
                    </span>
                  ) : (
                    <span className={styles.perspectiveUnset}>
                      Perspective not set
                    </span>
                  )}
                  {note.source ? (
                    <span className={styles.sourceLabel}>
                      Source: {note.source}
                    </span>
                  ) : null}
                </div>
                {note.tags && note.tags.length > 0 ? (
                  <p className={styles.tagsLabel}>
                    Tags: {note.tags.join(", ")}
                  </p>
                ) : null}
              </header>
              <p className={styles.excerptText}>{note.excerpt}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
