"use client";

import type { FallacyWarningModel } from "../copilot/components/types";

import { useMemo } from "react";

const SEVERITY_ORDER: Record<string, number> = {
  high: 3,
  medium: 2,
  low: 1,
};

const SEVERITY_LABELS: Record<string, string> = {
  high: "High severity",
  medium: "Medium severity",
  low: "Low severity",
};

const BADGE_CLASSES: Record<string, string> = {
  high: "badge badge-danger",
  medium: "badge badge-warning",
  low: "badge badge-secondary",
};

function normaliseSeverity(severity: string | null | undefined): "high" | "medium" | "low" {
  const value = (severity ?? "medium").toLowerCase();
  if (value === "high" || value === "medium" || value === "low") {
    return value;
  }
  return "medium";
}

function formatFallacyType(value: string): string {
  return value
    .split(/[\s_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export type FallacyWarningsProps = {
  warnings?: FallacyWarningModel[] | null;
  className?: string;
  title?: string;
};

export function FallacyWarnings({
  warnings,
  className,
  title = "Reasoning flags detected",
}: FallacyWarningsProps): JSX.Element | null {
  const items = useMemo(() => {
    if (!Array.isArray(warnings)) {
      return [] as Array<FallacyWarningModel & { severity: "high" | "medium" | "low" }>;
    }
    return warnings
      .map((warning) => ({
        ...warning,
        severity: normaliseSeverity(warning.severity),
      }))
      .filter((warning) => warning.fallacy_type && warning.description);
  }, [warnings]);

  if (items.length === 0) {
    return null;
  }

  const dominantSeverity = items.reduce<"high" | "medium" | "low">((current, warning) => {
    const warningRank = SEVERITY_ORDER[warning.severity] ?? 0;
    const currentRank = SEVERITY_ORDER[current] ?? 0;
    return warningRank > currentRank ? warning.severity : current;
  }, "low");

  const containerClass = [
    "chat-fallacy-warnings",
    `chat-fallacy-warnings--${dominantSeverity}`,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={containerClass} aria-live="polite">
      <header className="chat-fallacy-warnings__header">
        <h4 className="chat-fallacy-warnings__title">{title}</h4>
        <span className={BADGE_CLASSES[dominantSeverity] ?? "badge badge-warning"}>
          {SEVERITY_LABELS[dominantSeverity] ?? "Moderate severity"}
        </span>
      </header>
      <ul className="chat-fallacy-warnings__list">
        {items.map((warning, index) => {
          const badgeClass = BADGE_CLASSES[warning.severity] ?? "badge badge-warning";
          const suggestion = warning.suggestion?.trim();
          const matchedText = warning.matched_text?.trim();
          return (
            <li
              key={`${warning.fallacy_type}-${index}`}
              className="chat-fallacy-warnings__item"
            >
              <div className="chat-fallacy-warnings__itemHeader">
                <span className={badgeClass}>
                  {SEVERITY_LABELS[warning.severity] ?? "Moderate severity"}
                </span>
                <span className="chat-fallacy-warnings__type">
                  {formatFallacyType(warning.fallacy_type)}
                </span>
              </div>
              <p className="chat-fallacy-warnings__description">{warning.description}</p>
              {matchedText ? (
                <p className="chat-fallacy-warnings__context">
                  <span className="chat-fallacy-warnings__label">Example:</span>{" "}
                  <q>{matchedText}</q>
                </p>
              ) : null}
              {suggestion ? (
                <p className="chat-fallacy-warnings__suggestion">
                  <span className="chat-fallacy-warnings__label">Suggestion:</span>{" "}
                  {suggestion}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default FallacyWarnings;
