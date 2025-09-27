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
}: ContradictionsPanelClientProps) {
  const [viewingMode, setViewingMode] = useState<ViewingMode>("neutral");
  const [modeState, setModeState] = useState<ModeState>(() => initializeModeState());

  const shouldShowContradictions = useMemo(() => {
    if (viewingMode !== "apologetic") {
      return true;
    }
    return modeState.apologetic;
  }, [modeState.apologetic, viewingMode]);

  const visibleContradictions = useMemo(() => {
    if (!shouldShowContradictions) {
      return [] as ContradictionRecord[];
    }
    return contradictions;
  }, [contradictions, shouldShowContradictions]);

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

      </div>

      {!shouldShowContradictions ? (
        <p
          data-testid="contradictions-apologetic-hidden"
          style={{ margin: 0, color: "var(--muted-foreground, #475569)" }}
        >
          Contradictions are currently hidden in <strong>Apologetic</strong> mode. Enable the toggle above
          to include them while emphasizing harmonization evidence.
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
                    <Link href={item.source} target="_blank" rel="noreferrer" style={{ color: "#2563eb" }}>
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
