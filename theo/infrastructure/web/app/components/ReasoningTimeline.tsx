"use client";

import { useState } from "react";
import styles from "./ReasoningTimeline.module.css";

export type ReasoningStepType =
  | "understand"
  | "gather"
  | "tensions"
  | "draft"
  | "critique"
  | "revise"
  | "synthesize";

export type ReasoningStepStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "skipped";

export interface ReasoningStep {
  id: string;
  step_type: ReasoningStepType;
  status: ReasoningStepStatus;
  title: string;
  description?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  citations?: string[];
  tools_called?: string[];
  output_summary?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ReasoningTimeline {
  session_id: string;
  question: string;
  steps: ReasoningStep[];
  current_step_index: number;
  total_duration_ms: number;
  status: string;
  created_at: string;
  updated_at: string;
}

interface ReasoningTimelineProps {
  timeline: ReasoningTimeline;
  className?: string;
}

const STEP_ICONS: Record<ReasoningStepType, string> = {
  understand: "🔍",
  gather: "📚",
  tensions: "⚡",
  draft: "✏️",
  critique: "🔬",
  revise: "🔄",
  synthesize: "✨",
};

const STEP_LABELS: Record<ReasoningStepType, string> = {
  understand: "Understanding",
  gather: "Gathering Evidence",
  tensions: "Detecting Tensions",
  draft: "Drafting Answer",
  critique: "Critical Review",
  revise: "Revision",
  synthesize: "Synthesis",
};

function getStatusClass(status: ReasoningStepStatus): string {
  const classMap: Record<ReasoningStepStatus, string | undefined> = {
    pending: styles.statusPending,
    in_progress: styles.statusInProgress,
    completed: styles.statusCompleted,
    failed: styles.statusFailed,
    skipped: styles.statusSkipped,
  };
  return classMap[status] ?? "";
}

function formatDuration(durationMs: number | null | undefined): string {
  if (!durationMs || durationMs <= 0) return "";
  
  if (durationMs < 1000) {
    return `${durationMs}ms`;
  }
  
  const seconds = Math.floor(durationMs / 1000);
  if (seconds < 60) {
    return `${seconds}s`;
  }
  
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

function TimelineStep({
  step,
  isActive,
  stepNumber,
}: {
  step: ReasoningStep;
  isActive: boolean;
  stepNumber: number;
}) {
  const [isExpanded, setIsExpanded] = useState(isActive);
  
  const icon = STEP_ICONS[step.step_type] ?? "📍";
  const label = step.title || (STEP_LABELS[step.step_type] ?? step.step_type);
  const statusClass = getStatusClass(step.status);
  const duration = formatDuration(step.duration_ms);
  const hasCitations = Boolean(step.citations && step.citations.length > 0);
  const hasTools = step.tools_called && step.tools_called.length > 0;
  const hasDetails = step.description || hasCitations || hasTools || step.output_summary;

  return (
    <li className={`${styles.step} ${statusClass} ${isActive ? styles.active : ""}`}>
      <div
        className={styles.stepHeader}
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
        role={hasDetails ? "button" : undefined}
        tabIndex={hasDetails ? 0 : undefined}
        onKeyDown={(e) => {
          if (hasDetails && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
      >
        <span className={styles.stepNumber}>{stepNumber}</span>
        <span className={styles.stepIcon} aria-hidden="true">
          {icon}
        </span>
        <div className={styles.stepMeta}>
          <span className={styles.stepLabel}>{label}</span>
          {duration && <span className={styles.stepDuration}>{duration}</span>}
        </div>
        {step.status === "in_progress" && (
          <span className={styles.spinner} aria-label="In progress" />
        )}
        {hasDetails && (
          <span className={styles.expandIcon} aria-hidden="true">
            {isExpanded ? "▼" : "▶"}
          </span>
        )}
      </div>

      {isExpanded && hasDetails && (
        <div className={styles.stepDetails}>
          {step.description && (
            <p className={styles.stepDescription}>{step.description}</p>
          )}

          {step.output_summary && (
            <div className={styles.stepOutput}>
              <span className={styles.detailLabel}>Output:</span>
              <p>{step.output_summary}</p>
            </div>
          )}

          {hasCitations && (
            <div className={styles.stepCitations}>
              <span className={styles.detailLabel}>Citations:</span>
              <ul className={styles.citationList}>
                {step.citations!.map((citation, idx) => (
                  <li key={idx} className={styles.citationItem}>
                    {citation}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {hasTools && (
            <div className={styles.stepTools}>
              <span className={styles.detailLabel}>Tools used:</span>
              <div className={styles.toolsList}>
                {step.tools_called!.map((tool, idx) => (
                  <span key={idx} className={styles.toolBadge}>
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export function ReasoningTimeline({
  timeline,
  className,
}: ReasoningTimelineProps) {
  if (!timeline || !timeline.steps || timeline.steps.length === 0) {
    return null;
  }

  const totalDuration = formatDuration(timeline.total_duration_ms);
  const isRunning = timeline.status === "running";

  return (
    <section
      className={`${styles.timeline} ${className || ""}`}
      aria-label="Reasoning timeline"
    >
      <header className={styles.timelineHeader}>
        <h3 className={styles.timelineTitle}>Reasoning Timeline</h3>
        {totalDuration && !isRunning && (
          <span className={styles.totalDuration}>Total: {totalDuration}</span>
        )}
        {isRunning && (
          <span className={styles.statusBadge}>
            <span className={styles.spinner} aria-hidden="true" />
            Running...
          </span>
        )}
      </header>

      <ol className={styles.stepsList}>
        {timeline.steps.map((step, index) => (
          <TimelineStep
            key={step.id}
            step={step}
            isActive={index === timeline.current_step_index}
            stepNumber={index + 1}
          />
        ))}
      </ol>
    </section>
  );
}

export default ReasoningTimeline;
