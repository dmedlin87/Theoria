"use client";

import Link from "next/link";

import type { ContradictionRecord } from "./ContradictionsPanel";

const perspectiveOptions: { id: string; label: string; helper: string }[] = [
  {
    id: "skeptical",
    label: "Skeptical tensions",
    helper: "Highlights perceived contradictions raised by critical readers.",
  },
  {
    id: "apologetic",
    label: "Apologetic harmonies",
    helper: "Surfaces reconciliation proposals from harmonization traditions.",
  },
];

interface ContradictionsPanelClientProps {
  contradictions: ContradictionRecord[];
  selectedPerspectives: string[];
  onPerspectivesChange: (next: string[]) => void;
}

function togglePerspective(
  selected: string[],
  perspective: string,
  enabled: boolean,
): string[] {
  const normalized = perspective.toLowerCase();
  const current = new Set(selected.map((item) => item.toLowerCase()));
  if (enabled) {
    current.add(normalized);
  } else {
    current.delete(normalized);
  }
  return Array.from(current);
}

function normalizePerspective(value: string | undefined | null): string {
  return (value ?? "").toLowerCase();
}

function isLikelyUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return Boolean(parsed.protocol && parsed.host);
  } catch (error) {
    return false;
  }
}

export default function ContradictionsPanelClient({
  contradictions,
  selectedPerspectives,
  onPerspectivesChange,
}: ContradictionsPanelClientProps) {
  const selectedSet = new Set(selectedPerspectives.map((value) => value.toLowerCase()));
  const nothingSelected = selectedSet.size === 0;

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <fieldset
        style={{
          border: "1px solid var(--border, #dbeafe)",
          borderRadius: "0.75rem",
          padding: "1rem",
          margin: 0,
          background: "#f8fafc",
        }}
      >
        <legend style={{ fontWeight: 600 }}>Filter by perspective</legend>
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {perspectiveOptions.map((option) => (
            <label
              key={option.id}
              style={{ display: "grid", gap: "0.25rem" }}
            >
              <span style={{ fontWeight: 600 }}>{option.label}</span>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={selectedSet.has(option.id)}
                  onChange={(event) =>
                    onPerspectivesChange(
                      togglePerspective(selectedPerspectives, option.id, event.target.checked),
                    )
                  }
                  aria-label={`Toggle ${option.label}`}
                />
                <span style={{ fontSize: "0.875rem", color: "var(--muted-foreground, #475569)" }}>
                  {option.helper}
                </span>
              </div>
            </label>
          ))}
          <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--muted-foreground, #475569)" }}>
            Combine filters to compare skeptical critiques alongside apologetic responses for the selected
            passages.
          </p>
        </div>
      </fieldset>

      {nothingSelected ? (
        <p style={{ margin: 0, color: "var(--muted-foreground, #475569)" }}>
          No perspectives selected. Enable at least one filter above to load contradictions or harmonies.
        </p>
      ) : contradictions.length === 0 ? (
        <p style={{ margin: 0 }}>No entries match the chosen filters.</p>
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
          {contradictions.map((item) => (
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
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                  <p style={{ margin: 0, fontWeight: 600 }}>{item.summary}</p>
                  {item.perspective ? (
                    <span
                      style={{
                        display: "inline-block",
                        padding: "0.25rem 0.5rem",
                        borderRadius: "999px",
                        background:
                          normalizePerspective(item.perspective) === "apologetic"
                            ? "rgba(14, 159, 110, 0.16)"
                            : "rgba(239, 68, 68, 0.16)",
                        color:
                          normalizePerspective(item.perspective) === "apologetic"
                            ? "#047857"
                            : "#b91c1c",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                      }}
                    >
                      {item.perspective}
                    </span>
                  ) : null}
                </div>
                <p
                  style={{
                    margin: 0,
                    fontSize: "0.875rem",
                    color: "var(--muted-foreground, #4b5563)",
                  }}
                >
                  {item.osis[0]} ⇄ {item.osis[1]}
                </p>
              </header>

              {item.weight != null ? (
                <p
                  style={{
                    margin: 0,
                    fontSize: "0.8125rem",
                    color: "var(--muted-foreground, #475569)",
                  }}
                >
                  Weight: {item.weight.toFixed(2)}
                </p>
              ) : null}

              {item.tags && item.tags.length > 0 ? (
                <ul
                  style={{
                    listStyle: "none",
                    margin: 0,
                    padding: 0,
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "0.5rem",
                  }}
                >
                  {item.tags.map((tag) => (
                    <li
                      key={tag}
                      style={{
                        borderRadius: "999px",
                        background: "#e0f2fe",
                        color: "#0369a1",
                        fontSize: "0.75rem",
                        padding: "0.25rem 0.75rem",
                      }}
                    >
                      {tag}
                    </li>
                  ))}
                </ul>
              ) : null}

              {item.source ? (
                <p style={{ margin: 0, fontSize: "0.875rem" }}>
                  Source:{" "}
                  {isLikelyUrl(item.source) ? (
                    <Link
                      href={item.source}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "#2563eb" }}
                    >
                      {item.source}
                    </Link>
                  ) : (
                    <span>{item.source}</span>
                  )}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
