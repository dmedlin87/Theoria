"use client";

import { useEffect, useMemo, useState } from "react";

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

type PerspectiveFilter = "all" | "skeptical" | "apologetic" | "neutral";

const perspectiveOptions: { id: PerspectiveFilter; label: string }[] = [
  { id: "all", label: "All perspectives" },
  { id: "skeptical", label: "Skeptical only" },
  { id: "apologetic", label: "Apologetic only" },
  { id: "neutral", label: "Neutral only" },
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
  const [perspectiveFilter, setPerspectiveFilter] = useState<PerspectiveFilter>("all");
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);

  useEffect(() => {
    if (!features?.commentaries) {
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
        if (perspectiveFilter !== "all") {
          params.append("perspective", perspectiveFilter);
        }
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
  }, [baseUrl, features?.commentaries, mode.id, osis, perspectiveFilter]);

  if (!features?.commentaries) {
    return null;
  }

  return (
    <section
      aria-labelledby="commentaries-heading"
      style={{
        background: "#fff",
        borderRadius: "0.5rem",
        padding: "1rem",
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
      }}
    >
      <h3 id="commentaries-heading" style={{ marginTop: 0 }}>
        Commentaries & notes
      </h3>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}>
        Curated research notes anchored to <strong>{osis}</strong>.
      </p>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #64748b)", fontSize: "0.9rem" }}>
        {modeSummary}
      </p>
      <div
        style={{
          display: "flex",
          gap: "0.75rem",
          alignItems: "center",
          flexWrap: "wrap",
          marginBottom: "1rem",
        }}
      >
        <label style={{ display: "grid", gap: "0.25rem" }}>
          <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>Perspective filter</span>
          <select
            value={perspectiveFilter}
            onChange={(event) => setPerspectiveFilter(event.target.value as PerspectiveFilter)}
            style={{
              padding: "0.35rem 0.75rem",
              borderRadius: "0.375rem",
              border: "1px solid var(--border, #d1d5db)",
              fontSize: "0.875rem",
            }}
          >
            {perspectiveOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <ModeChangeBanner area="Commentaries" />
      </div>
      {loading ? (
        <p>Loading commentaries…</p>
      ) : error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
          Unable to load commentaries. {error}
        </p>
      ) : commentaries.length === 0 ? (
        <p>No commentaries recorded yet.</p>
      ) : (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "grid",
            gap: "1rem",
          }}
        >
          {commentaries.map((note) => (
            <li
              key={note.id}
              style={{
                border: "1px solid var(--border, #e5e7eb)",
                borderRadius: "0.5rem",
                padding: "0.75rem",
              }}
            >
              <header style={{ marginBottom: "0.5rem" }}>
                <h4 style={{ margin: "0 0 0.25rem" }}>{note.title ?? "Untitled commentary"}</h4>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--muted-foreground, #6b7280)" }}>
                    OSIS: {note.osis}
                  </span>
                  {note.perspective ? (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.25rem",
                        padding: "0.25rem 0.5rem",
                        borderRadius: "9999px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        background:
                          note.perspective === "apologetic"
                            ? "rgba(16, 185, 129, 0.18)"
                            : note.perspective === "skeptical"
                            ? "rgba(239, 68, 68, 0.18)"
                            : "rgba(148, 163, 184, 0.2)",
                        color:
                          note.perspective === "apologetic"
                            ? "#047857"
                            : note.perspective === "skeptical"
                            ? "#b91c1c"
                            : "#1e293b",
                      }}
                    >
                      {note.perspective}
                    </span>
                  ) : (
                    <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground, #6b7280)" }}>
                      Perspective not set
                    </span>
                  )}
                  {note.source ? (
                    <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground, #6b7280)" }}>
                      Source: {note.source}
                    </span>
                  ) : null}
                </div>
                {note.tags && note.tags.length > 0 ? (
                  <p style={{ margin: "0.35rem 0 0", fontSize: "0.75rem", color: "var(--muted-foreground, #4b5563)" }}>
                    Tags: {note.tags.join(", ")}
                  </p>
                ) : null}
              </header>
              <p style={{ margin: "0 0 0.5rem", lineHeight: 1.6 }}>{note.excerpt}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
