"use client";

import Link from "next/link";
import { useMemo } from "react";

import type { ContradictionRecord } from "./ContradictionsPanel";

export type ViewingMode = "neutral" | "skeptical" | "apologetic";

export type ModeState = Record<ViewingMode, boolean>;

export const viewingModes: { id: ViewingMode; label: string }[] = [
  { id: "neutral", label: "Neutral" },
  { id: "skeptical", label: "Skeptical" },
  { id: "apologetic", label: "Apologetic" },
];

export function initializeModeState(): ModeState {
  return {
    neutral: true,
    skeptical: true,
    apologetic: true,
  };
}

interface ContradictionsPanelClientProps {
  contradictions: ContradictionRecord[];
  viewingMode: ViewingMode;
  onViewingModeChange: (mode: ViewingMode) => void;
  modeState: ModeState;
  onModeStateChange: (state: ModeState) => void;
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
  viewingMode,
  onViewingModeChange,
  modeState,
  onModeStateChange,
}: ContradictionsPanelClientProps) {
  const visibleContradictions = useMemo(() => {
    return contradictions.filter((item) => {
      const perspective = (item.perspective ?? "neutral").toLowerCase();
      if (perspective === "skeptical") {
        return modeState.skeptical;
      }
      if (perspective === "apologetic") {
        return modeState.apologetic;
      }
      return modeState.neutral;
    });
  }, [contradictions, modeState]);

  const allHidden = useMemo(() => {
    const anySelected = Object.values(modeState).some(Boolean);
    return !anySelected;
  }, [modeState]);

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
            onChange={(event) => onViewingModeChange(event.target.value as ViewingMode)}
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
                    onModeStateChange({
                      ...modeState,
                      [mode.id]: event.target.checked,
                    })
                  }
                  aria-label={`Show contradictions in ${mode.label} mode`}
                />
                <span>
                  Show contradictions in <strong>{mode.label}</strong> mode
                </span>
              </label>
            ))}
            <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--muted-foreground, #475569)" }}>
              Toggle modes to tailor how contradictions and harmonies appear. For example, enable
              Apologetic visibility to inspect harmonization strategies alongside skeptical critiques.
            </p>
          </div>
        </fieldset>

      </div>

      {allHidden ? (
        <p
          data-testid="contradictions-apologetic-hidden"
          style={{ margin: 0, color: "var(--muted-foreground, #475569)" }}
        >
          All perspectives are currently hidden. Re-enable at least one toggle to surface contradictions and
          harmonies.
        </p>
      ) : visibleContradictions.length === 0 ? (
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
          {visibleContradictions.map((item) => (
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
                <p style={{ margin: 0, fontWeight: 600 }}>{item.summary}</p>
                <p
                  style={{
                    margin: 0,
                    fontSize: "0.875rem",
                    color: "var(--muted-foreground, #4b5563)",
                  }}
                >
                  {item.osis[0]} ⇄ {item.osis[1]}
                </p>
                {item.perspective ? (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.25rem",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color:
                        item.perspective === "apologetic"
                          ? "#047857"
                          : item.perspective === "skeptical"
                          ? "#b91c1c"
                          : "#1e293b",
                    }}
                  >
                    Perspective:
                    <span
                      style={{
                        borderRadius: "999px",
                        padding: "0.125rem 0.5rem",
                        background:
                          item.perspective === "apologetic"
                            ? "rgba(16, 185, 129, 0.15)"
                            : item.perspective === "skeptical"
                            ? "rgba(239, 68, 68, 0.12)"
                            : "rgba(148, 163, 184, 0.2)",
                      }}
                    >
                      {item.perspective}
                    </span>
                  </span>
                ) : null}
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
