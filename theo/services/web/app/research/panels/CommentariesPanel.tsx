"use client";

import { useEffect, useMemo, useState } from "react";

import ModeChangeBanner from "../../components/ModeChangeBanner";
import { formatEmphasisSummary } from "../../mode-config";
import { useMode } from "../../mode-context";
import { getApiBaseUrl } from "../../lib/api";
import type { ResearchFeatureFlags } from "../types";

const perspectiveFilters = [
  { id: "apologetic", label: "Apologetic" },
  { id: "skeptical", label: "Skeptical" },
];

interface CommentaryExcerpt {
  id: string;
  osis: string;
  title?: string | null;
  excerpt: string;
  source?: string | null;
  citation?: string | null;
  tradition?: string | null;
  perspective?: string | null;
  tags?: string[] | null;
}

interface CommentaryResponse {
  osis: string;
  items?: CommentaryExcerpt[] | null;
  total?: number | null;
}

interface CommentariesPanelProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default function CommentariesPanel({ osis, features }: CommentariesPanelProps) {
  const { mode } = useMode();
  const [commentaries, setCommentaries] = useState<CommentaryExcerpt[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedPerspectives, setSelectedPerspectives] = useState<string[]>([
    "apologetic",
    "skeptical",
  ]);
  const baseUrl = useMemo(() => getApiBaseUrl().replace(/\/$/, ""), []);
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);

  useEffect(() => {
    if (!features?.commentaries) {
      return;
    }

    let cancelled = false;
    const fetchCommentaries = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("osis", osis);
        selectedPerspectives.forEach((perspective) => {
          if (perspective) {
            params.append("perspective", perspective);
          }
        });
        const response = await fetch(`${baseUrl}/research/commentaries?${params.toString()}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error((await response.text()) || response.statusText);
        }
        const payload = (await response.json()) as CommentaryResponse;
        if (!cancelled) {
          setCommentaries(payload.items?.filter(Boolean) ?? []);
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

    void fetchCommentaries();
    return () => {
      cancelled = true;
    };
  }, [baseUrl, features?.commentaries, osis, selectedPerspectives]);

  if (!features?.commentaries) {
    return null;
  }

  const selectedSet = new Set(selectedPerspectives.map((value) => value.toLowerCase()));
  const nothingSelected = selectedSet.size === 0;

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
        Curated commentary excerpts anchored to <strong>{osis}</strong>.
      </p>
      <p style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #64748b)", fontSize: "0.9rem" }}>
        {modeSummary}
      </p>
      <ModeChangeBanner area="Commentaries" />

      <fieldset
        style={{
          border: "1px solid var(--border, #dbeafe)",
          borderRadius: "0.75rem",
          padding: "1rem",
          marginBottom: "1rem",
          background: "#f8fafc",
        }}
      >
        <legend style={{ fontWeight: 600 }}>Perspectives</legend>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          {perspectiveFilters.map((filter) => (
            <label key={filter.id} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={selectedSet.has(filter.id)}
                onChange={(event) => {
                  const next = new Set(selectedSet);
                  if (event.target.checked) {
                    next.add(filter.id);
                  } else {
                    next.delete(filter.id);
                  }
                  setSelectedPerspectives(Array.from(next));
                }}
                aria-label={`Toggle ${filter.label} perspective`}
              />
              <span>{filter.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {nothingSelected ? (
        <p style={{ margin: 0, color: "var(--muted-foreground, #475569)" }}>
          Select at least one perspective above to view commentary excerpts.
        </p>
      ) : loading ? (
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
          {commentaries.map((entry) => (
            <li
              key={entry.id}
              style={{
                border: "1px solid var(--border, #e5e7eb)",
                borderRadius: "0.5rem",
                padding: "0.75rem",
                display: "grid",
                gap: "0.5rem",
              }}
            >
              <header>
                <h4 style={{ margin: "0 0 0.25rem" }}>{entry.title ?? "Untitled excerpt"}</h4>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                  {entry.perspective ? (
                    <span
                      style={{
                        display: "inline-block",
                        padding: "0.25rem 0.5rem",
                        borderRadius: "999px",
                        background:
                          entry.perspective.toLowerCase() === "apologetic"
                            ? "rgba(14, 159, 110, 0.16)"
                            : "rgba(239, 68, 68, 0.16)",
                        color:
                          entry.perspective.toLowerCase() === "apologetic"
                            ? "#047857"
                            : "#b91c1c",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                      }}
                    >
                      {entry.perspective}
                    </span>
                  ) : (
                    <span style={{ fontSize: "0.8rem", color: "var(--muted-foreground, #6b7280)" }}>
                      Perspective not set
                    </span>
                  )}
                  {entry.tradition ? (
                    <span style={{ fontSize: "0.8rem", color: "var(--muted-foreground, #6b7280)" }}>
                      Tradition: {entry.tradition}
                    </span>
                  ) : null}
                  {entry.tags && entry.tags.length > 0 ? (
                    <span style={{ fontSize: "0.8rem", color: "var(--muted-foreground, #6b7280)" }}>
                      Tags: {entry.tags.join(", ")}
                    </span>
                  ) : null}
                </div>
              </header>
              <blockquote style={{ margin: 0, lineHeight: 1.6 }}>{entry.excerpt}</blockquote>
              <footer style={{ fontSize: "0.85rem", color: "var(--muted-foreground, #4b5563)" }}>
                {entry.source ?? "Unspecified source"}
                {entry.citation ? ` • ${entry.citation}` : ""}
              </footer>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
