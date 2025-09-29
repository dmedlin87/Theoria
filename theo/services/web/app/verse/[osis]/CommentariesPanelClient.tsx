"use client";

import { useMemo, useState } from "react";

import type { CommentaryRecord } from "./CommentariesPanel";

type PerspectiveFilter = "all" | "skeptical" | "apologetic" | "neutral";

interface CommentariesPanelClientProps {
  commentaries: CommentaryRecord[];
}

function normalizePerspective(value: string | null | undefined): PerspectiveFilter {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "skeptical") {
    return "skeptical";
  }
  if (normalized === "apologetic") {
    return "apologetic";
  }
  if (normalized === "neutral") {
    return "neutral";
  }
  return "neutral";
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export default function CommentariesPanelClient({ commentaries }: CommentariesPanelClientProps) {
  const [perspective, setPerspective] = useState<PerspectiveFilter>("all");
  const [tagQuery, setTagQuery] = useState<string>("");

  const normalizedTag = tagQuery.trim().toLowerCase();

  const filteredCommentaries = useMemo(() => {
    return commentaries.filter((item) => {
      const itemPerspective = normalizePerspective(item.perspective);
      if (perspective !== "all" && itemPerspective !== perspective) {
        return false;
      }
      if (!normalizedTag) {
        return true;
      }
      return (item.tags ?? []).some((tag) => tag.toLowerCase().includes(normalizedTag));
    });
  }, [commentaries, normalizedTag, perspective]);

  if (commentaries.length === 0) {
    return <p>No commentaries recorded yet.</p>;
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div
        style={{
          display: "grid",
          gap: "0.75rem",
          background: "#f8fafc",
          padding: "0.75rem",
          borderRadius: "0.5rem",
        }}
      >
        <label style={{ display: "grid", gap: "0.25rem" }}>
          <span style={{ fontWeight: 600 }}>Perspective filter</span>
          <select
            value={perspective}
            onChange={(event) => setPerspective(event.target.value as PerspectiveFilter)}
            style={{
              padding: "0.25rem 0.5rem",
              borderRadius: "0.375rem",
              border: "1px solid var(--border, #cbd5f5)",
            }}
          >
            <option value="all">Show all perspectives</option>
            <option value="apologetic">Apologetic</option>
            <option value="skeptical">Skeptical</option>
            <option value="neutral">Neutral</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: "0.25rem" }}>
          <span style={{ fontWeight: 600 }}>Filter by tag</span>
          <input
            type="search"
            value={tagQuery}
            onChange={(event) => setTagQuery(event.target.value)}
            placeholder="e.g. resurrection"
            style={{
              padding: "0.25rem 0.5rem",
              borderRadius: "0.375rem",
              border: "1px solid var(--border, #dbeafe)",
            }}
          />
        </label>
      </div>

      {filteredCommentaries.length === 0 ? (
        <p style={{ margin: 0 }}>No commentaries match the selected filters.</p>
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
          {filteredCommentaries.map((item) => {
            const itemPerspective = normalizePerspective(item.perspective);
            return (
              <li
                key={item.id}
                style={{
                  border: "1px solid var(--border, #e5e7eb)",
                  borderRadius: "0.75rem",
                  padding: "1rem",
                  display: "grid",
                  gap: "0.75rem",
                }}
              >
                <header style={{ display: "grid", gap: "0.25rem" }}>
                  <h4 style={{ margin: 0 }}>{item.title ?? "Untitled commentary"}</h4>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "0.875rem",
                      color: "var(--muted-foreground, #475569)",
                    }}
                  >
                    Perspective: <strong>{titleCase(itemPerspective)}</strong>
                  </p>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "0.75rem",
                      color: "var(--muted-foreground, #64748b)",
                    }}
                  >
                    OSIS anchor: {item.osis}
                  </p>
                </header>
                <p style={{ margin: 0, lineHeight: 1.6 }}>{item.excerpt}</p>
                <footer style={{ display: "grid", gap: "0.5rem" }}>
                  {item.tags && item.tags.length > 0 ? (
                    <ul
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "0.5rem",
                        padding: 0,
                        margin: 0,
                        listStyle: "none",
                      }}
                    >
                      {item.tags.map((tag) => (
                        <li
                          key={`${item.id}-${tag}`}
                          style={{
                            background: "#e0f2fe",
                            color: "#0369a1",
                            padding: "0.25rem 0.75rem",
                            borderRadius: "999px",
                            fontSize: "0.75rem",
                          }}
                        >
                          {tag}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "0.5rem",
                      fontSize: "0.75rem",
                      color: "var(--muted-foreground, #4b5563)",
                    }}
                  >
                    {item.source ? <span>Source: {item.source}</span> : null}
                    {item.citation ? <span>Citation: {item.citation}</span> : null}
                  </div>
                </footer>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
