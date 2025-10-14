"use client";

import Link from "next/link";
import { useMemo } from "react";
import styles from "./ContradictionsPanelClient.module.css";

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
  } catch {
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
    <div className={styles.container}>
      <div className={styles.filterSection}>
        <label className={styles.formLabel}>
          <span className={styles.labelText}>Viewing mode</span>
          <select
            aria-label="Select viewing mode"
            value={viewingMode}
            onChange={(event) => onViewingModeChange(event.target.value as ViewingMode)}
            className={styles.select}
          >
            {viewingModes.map((mode) => (
              <option key={mode.id} value={mode.id}>
                {mode.label}
              </option>
            ))}
          </select>
        </label>

        <fieldset className={styles.fieldset}>
          <legend className={styles.legend}>Visibility preferences</legend>
          <div className={styles.checkboxGroup}>
            {viewingModes.map((mode) => (
              <label key={mode.id} className={styles.checkboxLabel}>
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
            <p className={styles.helperText}>
              Toggle modes to tailor how contradictions and harmonies appear. For example, enable
              Apologetic visibility to inspect harmonization strategies alongside skeptical critiques.
            </p>
          </div>
        </fieldset>

      </div>

      {allHidden ? (
        <p
          data-testid="contradictions-apologetic-hidden"
          className={styles.hiddenMessage}
        >
          All perspectives are currently hidden. Re-enable at least one toggle to surface contradictions and
          harmonies.
        </p>
      ) : visibleContradictions.length === 0 ? (
        <p className={styles.emptyMessage}>No contradictions match the selected filters.</p>
      ) : (
        <ul className={styles.contradictionsList}>
          {visibleContradictions.map((item) => (
            <li
              key={item.id}
              className={styles.contradictionCard}
            >
              <header className={styles.cardHeader}>
                <p className={styles.cardSummary}>{item.summary}</p>
                <p className={styles.osisLabel}>
                  {item.osis[0]} ⇄ {item.osis[1]}
                </p>
                {item.perspective ? (
                  <span
                    className={`${styles.perspectiveContainer} ${styles[item.perspective]}`}
                  >
                    Perspective:
                    <span
                      className={`${styles.perspectiveBadge} ${styles[item.perspective]}`}
                    >
                      {item.perspective}
                    </span>
                  </span>
                ) : null}
              </header>

              {item.weight != null ? (
                <p className={styles.weightLabel}>
                  Weight: {item.weight.toFixed(2)}
                </p>
              ) : null}

              {item.tags && item.tags.length > 0 ? (
                <ul className={styles.tagsList}>
                  {item.tags.map((tag) => (
                    <li
                      key={tag}
                      className={styles.tag}
                    >
                      {tag}
                    </li>
                  ))}
                </ul>
              ) : null}

              {item.source ? (
                <p className={styles.sourceLabel}>
                  Source:{" "}
                  {isLikelyUrl(item.source) ? (
                    <Link
                      href={item.source}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.sourceLink}
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
