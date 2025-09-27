"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { ContradictionRecord } from "./ContradictionsPanel";

type ViewingMode = "neutral" | "skeptical" | "apologetic";

type ModeState = Record<ViewingMode, boolean>;

const viewingModes: { id: ViewingMode; label: string }[] = [
  { id: "neutral", label: "Neutral" },
  { id: "skeptical", label: "Skeptical" },
  { id: "apologetic", label: "Apologetic" },
];

const severityDescriptions: Record<string, string> = {
  low: "Low severity: differences are usually reconciled with minor contextual notes.",
  medium: "Medium severity: requires careful harmonization and may remain debated.",
  high: "High severity: strongly conflicting claims with limited harmonization paths.",
};

function getSeverityLabel(severity?: string | null): string {
  if (!severity) {
    return "Unrated";
  }
  const normalized = severity.toLowerCase();
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function getSeverityDescription(severity?: string | null): string {
  if (!severity) {
    return "Severity indicates how difficult the passages are to reconcile.";
  }
  const normalized = severity.toLowerCase();
  return (
    severityDescriptions[normalized] ??
    "Severity indicates how difficult the passages are to reconcile."
  );
}

function getSeverityColor(severity?: string | null): string {
  if (!severity) {
    return "#94a3b8";
  }
  const normalized = severity.toLowerCase();
  switch (normalized) {
    case "low":
      return "#16a34a";
    case "medium":
      return "#f59e0b";
    case "high":
      return "#dc2626";
    default:
      return "#6366f1";
  }
}

function initializeModeState(): ModeState {
  return {
    neutral: true,
    skeptical: true,
    apologetic: false,
  };
}

interface ContradictionsPanelClientProps {
  contradictions: ContradictionRecord[];
}

export default function ContradictionsPanelClient({
  contradictions,
}: ContradictionsPanelClientProps) {
  const [viewingMode, setViewingMode] = useState<ViewingMode>("neutral");
  const [modeState, setModeState] = useState<ModeState>(() => initializeModeState());
  const [selectedSeverities, setSelectedSeverities] = useState<Set<string>>(
    () => new Set(),
  );

  const severities = useMemo(() => {
    const unique = new Set<string>();
    contradictions.forEach((item) => {
      if (item.severity) {
        unique.add(item.severity.toLowerCase());
      }
    });
    return Array.from(unique.values());
  }, [contradictions]);

  const shouldShowContradictions =
    viewingMode !== "apologetic" || modeState.apologetic;

  const filteredContradictions = useMemo(() => {
    if (selectedSeverities.size === 0) {
      return contradictions;
    }
    return contradictions.filter((item) => {
      if (!item.severity) {
        return selectedSeverities.has("unrated");
      }
      return selectedSeverities.has(item.severity.toLowerCase());
    });
  }, [contradictions, selectedSeverities]);

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
          <span style={{ fontWeight: 600 }}>Viewing mode</span>
          <select
            aria-label="Select viewing mode"
            value={viewingMode}
            onChange={(event) => setViewingMode(event.target.value as ViewingMode)}
            style={{
              padding: "0.25rem 0.5rem",
              borderRadius: "0.375rem",
              border: "1px solid var(--border, #cbd5f5)",
            }}
          >
            {viewingModes.map((mode) => (
              <option key={mode.id} value={mode.id}>
                {mode.label}
              </option>
            ))}
          </select>
        </label>

        <fieldset
          style={{
            border: "1px solid var(--border, #dbeafe)",
            borderRadius: "0.5rem",
            padding: "0.75rem",
            margin: 0,
          }}
        >
          <legend style={{ fontWeight: 600 }}>Visibility preferences</legend>
          <div style={{ display: "grid", gap: "0.5rem" }}>
            {viewingModes.map((mode) => (
              <label key={mode.id} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={modeState[mode.id]}
                  onChange={(event) =>
                    setModeState((prev) => ({
                      ...prev,
                      [mode.id]: event.target.checked,
                    }))
                  }
                  aria-label={`Show contradictions in ${mode.label} mode`}
                />
                <span>
                  Show contradictions in <strong>{mode.label}</strong> mode
                </span>
              </label>
            ))}
            <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--muted-foreground, #475569)" }}>
              Toggle modes to tailor how contradictions appear. For example, enable Apologetic
              visibility to audit harmonization strategies without leaving this view.
            </p>
          </div>
        </fieldset>

        {severities.length > 0 ? (
          <fieldset
            style={{
              border: "1px solid var(--border, #dbeafe)",
              borderRadius: "0.5rem",
              padding: "0.75rem",
              margin: 0,
              display: "grid",
              gap: "0.5rem",
            }}
          >
            <legend style={{ fontWeight: 600 }}>Filter by severity</legend>
            <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--muted-foreground, #475569)" }}>
              Use severity filters to focus on the most critical tensions first.
            </p>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "0.5rem",
              }}
            >
              {severities.map((severity) => {
                const normalized = severity.toLowerCase();
                const isSelected = selectedSeverities.has(normalized);
                return (
                  <button
                    key={severity}
                    type="button"
                    onClick={() => {
                      setSelectedSeverities((prev) => {
                        const next = new Set(prev);
                        if (isSelected) {
                          next.delete(normalized);
                        } else {
                          next.add(normalized);
                        }
                        return next;
                      });
                    }}
                    style={{
                      border: `1px solid ${getSeverityColor(normalized)}`,
                      background: isSelected ? `${getSeverityColor(normalized)}22` : "transparent",
                      color: getSeverityColor(normalized),
                      borderRadius: "999px",
                      padding: "0.25rem 0.75rem",
                      cursor: "pointer",
                    }}
                  >
                    {getSeverityLabel(normalized)}
                  </button>
                );
              })}
              {contradictions.some((item) => !item.severity) ? (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedSeverities((prev) => {
                      const next = new Set(prev);
                      if (next.has("unrated")) {
                        next.delete("unrated");
                      } else {
                        next.add("unrated");
                      }
                      return next;
                    });
                  }}
                  style={{
                    border: "1px solid #94a3b8",
                    background: selectedSeverities.has("unrated") ? "#94a3b822" : "transparent",
                    color: "#475569",
                    borderRadius: "999px",
                    padding: "0.25rem 0.75rem",
                    cursor: "pointer",
                  }}
                >
                  Unrated
                </button>
              ) : null}
            </div>
          </fieldset>
        ) : null}
      </div>

      {!shouldShowContradictions ? (
        <p
          data-testid="contradictions-apologetic-hidden"
          style={{ margin: 0, color: "var(--muted-foreground, #475569)" }}
        >
          Contradictions are currently hidden in <strong>Apologetic</strong> mode. Enable the toggle above
          to include them while emphasizing harmonization evidence.
        </p>
      ) : filteredContradictions.length === 0 ? (
        <p style={{ margin: 0 }}>No contradictions match the selected filters.</p>
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
          {filteredContradictions.map((item, index) => (
            <li
              key={`${item.summary}-${index}`}
              style={{
                border: "1px solid var(--border, #e5e7eb)",
                borderRadius: "0.75rem",
                padding: "1rem",
                display: "grid",
                gap: "0.75rem",
              }}
            >
              <header style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
                <p style={{ margin: 0, fontWeight: 600, flex: "1 1 auto" }}>{item.summary}</p>
                <span
                  title={`${getSeverityLabel(item.severity)} severity. ${getSeverityDescription(item.severity)}`}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.25rem",
                    background: `${getSeverityColor(item.severity)}22`,
                    color: getSeverityColor(item.severity),
                    borderRadius: "999px",
                    padding: "0.25rem 0.75rem",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                  }}
                >
                  Severity: {getSeverityLabel(item.severity)}
                </span>
              </header>

              <p
                style={{
                  margin: 0,
                  fontSize: "0.875rem",
                  color: "var(--muted-foreground, #4b5563)",
                }}
              >
                {item.osis[0]} ⇄ {item.osis[1]}
              </p>

              {item.snippet_pairs && item.snippet_pairs.length > 0 ? (
                <div style={{ display: "grid", gap: "0.75rem" }}>
                  {item.snippet_pairs.map((pair, pairIndex) => (
                    <div
                      key={pairIndex}
                      style={{
                        display: "grid",
                        gap: "0.75rem",
                        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                      }}
                    >
                      {pair.left ? (
                        <article
                          style={{
                            background: "#f1f5f9",
                            borderRadius: "0.5rem",
                            padding: "0.75rem",
                          }}
                        >
                          <header
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "baseline",
                              gap: "0.5rem",
                              marginBottom: "0.5rem",
                            }}
                          >
                            <strong>{pair.left.osis}</strong>
                            <Link
                              href={`/verse/${encodeURIComponent(pair.left.osis)}`}
                              style={{ fontSize: "0.75rem" }}
                            >
                              Open verse
                            </Link>
                          </header>
                          <p style={{ margin: 0, fontSize: "0.875rem", lineHeight: 1.5 }}>
                            {pair.left.text}
                          </p>
                        </article>
                      ) : null}

                      {pair.right ? (
                        <article
                          style={{
                            background: "#f1f5f9",
                            borderRadius: "0.5rem",
                            padding: "0.75rem",
                          }}
                        >
                          <header
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "baseline",
                              gap: "0.5rem",
                              marginBottom: "0.5rem",
                            }}
                          >
                            <strong>{pair.right.osis}</strong>
                            <Link
                              href={`/verse/${encodeURIComponent(pair.right.osis)}`}
                              style={{ fontSize: "0.75rem" }}
                            >
                              Open verse
                            </Link>
                          </header>
                          <p style={{ margin: 0, fontSize: "0.875rem", lineHeight: 1.5 }}>
                            {pair.right.text}
                          </p>
                        </article>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}

              {item.sources && item.sources.length > 0 ? (
                <div style={{ display: "grid", gap: "0.5rem" }}>
                  <p style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>
                    Supporting evidence
                  </p>
                  <ul style={{ margin: 0, paddingLeft: "1rem", display: "grid", gap: "0.25rem" }}>
                    {item.sources.map((source, sourceIndex) => (
                      <li key={source.url ?? sourceIndex}>
                        <Link
                          href={source.url ?? "#"}
                          target={source.url ? "_blank" : undefined}
                          rel={source.url ? "noreferrer" : undefined}
                          style={{ color: "#2563eb" }}
                        >
                          {source.label ?? source.url ?? "Evidence"}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
