"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { DragEvent } from "react";

import type {
  ResearchPlan,
  ResearchPlanStepStatus,
  ResearchPlanStepSkipPayload,
  ResearchPlanStepUpdatePayload,
} from "../lib/api-client";

import styles from "./PlanPanel.module.css";

const STATUS_LABELS: Record<ResearchPlanStepStatus, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
  skipped: "Skipped",
  blocked: "Blocked",
};

type EditableFields = {
  query: string;
  tool: string;
  status: ResearchPlanStepStatus;
  estimatedTokens: string;
  estimatedCostUsd: string;
  estimatedDurationSeconds: string;
};

type PlanPanelProps = {
  plan: ResearchPlan | null;
  isUpdating: boolean;
  errorMessage: string | null;
  disabled?: boolean;
  onReorder(order: string[]): void | Promise<void>;
  onUpdateStep(stepId: string, changes: ResearchPlanStepUpdatePayload): void | Promise<void>;
  onSkipStep(stepId: string, payload: ResearchPlanStepSkipPayload): void | Promise<void>;
};

function formatNumber(value: number | null | undefined, options?: Intl.NumberFormatOptions): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat(undefined, options).format(value);
}

function coerceNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatRelativeTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  const diffMilliseconds = date.getTime() - Date.now();
  const absMs = Math.abs(diffMilliseconds);
  const units: Array<{ unit: Intl.RelativeTimeFormatUnit; ms: number }> = [
    { unit: "year", ms: 1000 * 60 * 60 * 24 * 365 },
    { unit: "month", ms: 1000 * 60 * 60 * 24 * 30 },
    { unit: "week", ms: 1000 * 60 * 60 * 24 * 7 },
    { unit: "day", ms: 1000 * 60 * 60 * 24 },
    { unit: "hour", ms: 1000 * 60 * 60 },
    { unit: "minute", ms: 1000 * 60 },
    { unit: "second", ms: 1000 },
  ];
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const { unit, ms } of units) {
    if (absMs >= ms || unit === "second") {
      const valueInUnit = Math.round(diffMilliseconds / ms);
      if (valueInUnit === 0 && unit !== "second") {
        continue;
      }
      return formatter.format(valueInUnit, unit);
    }
  }
  return formatter.format(0, "second");
}

const STATUS_OPTIONS: ResearchPlanStepStatus[] = [
  "in_progress",
  "pending",
  "completed",
  "blocked",
  "skipped",
];

export default function PlanPanel({
  plan,
  isUpdating,
  errorMessage,
  disabled = false,
  onReorder,
  onUpdateStep,
  onSkipStep,
}: PlanPanelProps): JSX.Element {
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [draggingStepId, setDraggingStepId] = useState<string | null>(null);
  const [formState, setFormState] = useState<EditableFields | null>(null);

  const activeStep = useMemo(() => {
    if (!plan?.activeStepId) {
      return null;
    }
    return plan.steps.find((step) => step.id === plan.activeStepId) ?? null;
  }, [plan]);

  useEffect(() => {
    if (!editingStepId || !plan) {
      return;
    }
    const step = plan.steps.find((candidate) => candidate.id === editingStepId);
    if (!step) {
      setEditingStepId(null);
      setFormState(null);
      return;
    }
    setFormState({
      query: step.query ?? "",
      tool: step.tool ?? "",
      status: step.status,
      estimatedTokens: step.estimatedTokens != null ? String(step.estimatedTokens) : "",
      estimatedCostUsd: step.estimatedCostUsd != null ? String(step.estimatedCostUsd) : "",
      estimatedDurationSeconds:
        step.estimatedDurationSeconds != null ? String(step.estimatedDurationSeconds) : "",
    });
  }, [editingStepId, plan]);

  const handleEdit = useCallback((stepId: string) => {
    setEditingStepId(stepId);
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingStepId(null);
    setFormState(null);
  }, []);

  const handleInputChange = useCallback(
    (field: keyof EditableFields, value: string) => {
      setFormState((previous) => {
        if (!previous) {
          return previous;
        }
        return { ...previous, [field]: value };
      });
    },
    [],
  );

  const handleSave = useCallback(async () => {
    if (!plan || !editingStepId || !formState || disabled) {
      return;
    }
    const step = plan.steps.find((candidate) => candidate.id === editingStepId);
    if (!step) {
      return;
    }
    const changes: ResearchPlanStepUpdatePayload = {};
    const trimmedQuery = formState.query.trim();
    if ((trimmedQuery || null) !== (step.query ?? null)) {
      changes.query = trimmedQuery || null;
    }
    const trimmedTool = formState.tool.trim();
    if ((trimmedTool || null) !== (step.tool ?? null)) {
      changes.tool = trimmedTool || null;
    }
    if (formState.status !== step.status) {
      changes.status = formState.status;
    }
    const estimatedTokens = coerceNumber(formState.estimatedTokens);
    if (estimatedTokens !== (step.estimatedTokens ?? null)) {
      changes.estimatedTokens = estimatedTokens;
    }
    const estimatedCost = coerceNumber(formState.estimatedCostUsd);
    if (estimatedCost !== (step.estimatedCostUsd ?? null)) {
      changes.estimatedCostUsd = estimatedCost;
    }
    const estimatedDuration = coerceNumber(formState.estimatedDurationSeconds);
    if (estimatedDuration !== (step.estimatedDurationSeconds ?? null)) {
      changes.estimatedDurationSeconds = estimatedDuration;
    }
    if (Object.keys(changes).length === 0) {
      setEditingStepId(null);
      setFormState(null);
      return;
    }
    await onUpdateStep(step.id, changes);
    setEditingStepId(null);
    setFormState(null);
  }, [disabled, editingStepId, formState, onUpdateStep, plan]);

  const handleSkip = useCallback(
    async (stepId: string) => {
      if (disabled) {
        return;
      }
      let reason: string | null = null;
      if (typeof window !== "undefined") {
        // prompt provides a lightweight way to capture optional context
        const input = window.prompt("Skip reason (optional)", "");
        if (input != null) {
          reason = input.trim() ? input.trim() : null;
        }
      }
      await onSkipStep(stepId, { reason });
    },
    [disabled, onSkipStep],
  );

  const handleDragStart = useCallback(
    (stepId: string, event: DragEvent<HTMLLIElement>) => {
      if (disabled) {
        event.preventDefault();
        return;
      }
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", stepId);
      setDraggingStepId(stepId);
    },
    [disabled],
  );

  const handleDragEnd = useCallback(() => {
    setDraggingStepId(null);
  }, []);

  const handleDrop = useCallback(
    (targetId: string) => {
      if (!plan || !draggingStepId || draggingStepId === targetId || disabled) {
        return;
      }
      const order = plan.steps.map((step) => step.id);
      const fromIndex = order.indexOf(draggingStepId);
      const toIndex = order.indexOf(targetId);
      if (fromIndex === -1 || toIndex === -1) {
        setDraggingStepId(null);
        return;
      }
      const nextOrder = [...order];
      nextOrder.splice(fromIndex, 1);
      nextOrder.splice(toIndex, 0, draggingStepId);
      setDraggingStepId(null);
      void onReorder(nextOrder);
    },
    [disabled, draggingStepId, onReorder, plan],
  );

  const handleKeyboardMove = useCallback(
    (stepId: string, direction: -1 | 1) => {
      if (!plan || disabled) {
        return;
      }
      const order = plan.steps.map((step) => step.id);
      const currentIndex = order.indexOf(stepId);
      const nextIndex = currentIndex + direction;
      if (currentIndex === -1 || nextIndex < 0 || nextIndex >= order.length) {
        return;
      }
      const nextOrder = [...order];
      const [item] = nextOrder.splice(currentIndex, 1);
      nextOrder.splice(nextIndex, 0, item);
      void onReorder(nextOrder);
    },
    [disabled, onReorder, plan],
  );

  const panelDescription = plan
    ? `Research plan with ${plan.steps.length} steps${activeStep ? `; current step ${activeStep.label}` : ""}`
    : "Research plan pending";

  return (
    <section
      className={styles.panel}
      aria-labelledby="plan-panel-heading"
      aria-live="polite"
      aria-busy={isUpdating}
    >
      <header className={styles.header}>
        <div>
          <h2 id="plan-panel-heading">Live research plan</h2>
          <p className={styles.caption}>{panelDescription}</p>
        </div>
        <dl className={styles.metadata}>
          <div>
            <dt>Version</dt>
            <dd>{plan?.version ?? "—"}</dd>
          </div>
          <div>
            <dt>Last updated</dt>
            <dd>{formatRelativeTime(plan?.updatedAt)}</dd>
          </div>
        </dl>
      </header>

      {errorMessage ? (
        <div role="alert" className={styles.error}>
          {errorMessage}
        </div>
      ) : null}

      {isUpdating ? <div className={styles.progress}>Syncing plan…</div> : null}

      {plan && plan.steps.length ? (
        <ol className={styles.stepList} aria-disabled={disabled}>
          {plan.steps.map((step, index) => {
            const isEditing = editingStepId === step.id;
            const isActive = plan.activeStepId === step.id;
            const estimatedCost = formatNumber(step.estimatedCostUsd, {
              style: "currency",
              currency: "USD",
              minimumFractionDigits: 2,
            });
            const estimatedDuration = step.estimatedDurationSeconds
              ? `${formatNumber(step.estimatedDurationSeconds, { maximumFractionDigits: 1 })}s`
              : "—";
            const estimatedTokens = formatNumber(step.estimatedTokens, { maximumFractionDigits: 0 });
            return (
              <li
                key={step.id}
                data-step-id={step.id}
                className={[
                  styles.step,
                  draggingStepId === step.id ? styles.dragging : "",
                  isActive ? styles.active : "",
                ].join(" ")}
                draggable={!disabled}
                onDragStart={(event) => handleDragStart(step.id, event)}
                onDragEnd={handleDragEnd}
                onDragOver={(event) => {
                  event.preventDefault();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  handleDrop(step.id);
                }}
              >
                <div className={styles.stepHeader}>
                  <span className={styles.stepIndex} aria-hidden="true">
                    {index + 1}
                  </span>
                  <div className={styles.stepTitleGroup}>
                    <p className={styles.stepLabel}>{step.label}</p>
                    <span className={`${styles.status} ${styles[`status${step.status}`]}`}>
                      {STATUS_LABELS[step.status]}
                    </span>
                    {isActive ? <span className={styles.activeBadge}>Active</span> : null}
                  </div>
                  <div className={styles.stepActions}>
                    <button
                      type="button"
                      onClick={() => handleKeyboardMove(step.id, -1)}
                      disabled={disabled || isUpdating || index === 0}
                      aria-label="Move step up"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      onClick={() => handleKeyboardMove(step.id, 1)}
                      disabled={disabled || isUpdating || index === plan.steps.length - 1}
                      aria-label="Move step down"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      onClick={() => handleEdit(step.id)}
                      disabled={disabled || isUpdating}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSkip(step.id)}
                      disabled={disabled || isUpdating}
                    >
                      Skip
                    </button>
                  </div>
                </div>

                <dl className={styles.metrics}>
                  <div>
                    <dt>Est. tokens</dt>
                    <dd>{estimatedTokens}</dd>
                  </div>
                  <div>
                    <dt>Est. duration</dt>
                    <dd>{estimatedDuration}</dd>
                  </div>
                  <div>
                    <dt>Est. cost</dt>
                    <dd>{estimatedCost}</dd>
                  </div>
                </dl>

                {isEditing && formState ? (
                  <form
                    className={styles.editForm}
                    onSubmit={(event) => {
                      event.preventDefault();
                      void handleSave();
                    }}
                  >
                    <label className={styles.formField}>
                      <span>Query</span>
                      <textarea
                        value={formState.query}
                        onChange={(event) => handleInputChange("query", event.target.value)}
                        rows={3}
                      />
                    </label>
                    <label className={styles.formField}>
                      <span>Tool</span>
                      <input
                        type="text"
                        value={formState.tool}
                        onChange={(event) => handleInputChange("tool", event.target.value)}
                      />
                    </label>
                    <label className={styles.formField}>
                      <span>Status</span>
                      <select
                        value={formState.status}
                        onChange={(event) =>
                          handleInputChange("status", event.target.value as ResearchPlanStepStatus)
                        }
                      >
                        {STATUS_OPTIONS.map((option) => (
                          <option key={option} value={option}>
                            {STATUS_LABELS[option]}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className={styles.formGrid}>
                      <label className={styles.formField}>
                        <span>Est. tokens</span>
                        <input
                          type="number"
                          min={0}
                          value={formState.estimatedTokens}
                          onChange={(event) => handleInputChange("estimatedTokens", event.target.value)}
                        />
                      </label>
                      <label className={styles.formField}>
                        <span>Est. cost (USD)</span>
                        <input
                          type="number"
                          min={0}
                          step={0.01}
                          value={formState.estimatedCostUsd}
                          onChange={(event) => handleInputChange("estimatedCostUsd", event.target.value)}
                        />
                      </label>
                      <label className={styles.formField}>
                        <span>Est. duration (s)</span>
                        <input
                          type="number"
                          min={0}
                          step={0.1}
                          value={formState.estimatedDurationSeconds}
                          onChange={(event) =>
                            handleInputChange("estimatedDurationSeconds", event.target.value)
                          }
                        />
                      </label>
                    </div>
                    <div className={styles.formButtons}>
                      <button type="submit" disabled={isUpdating}>
                        Save
                      </button>
                      <button type="button" onClick={handleCancelEdit}>
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className={styles.summary}>
                    <p>
                      <span className={styles.summaryLabel}>Query:</span>{" "}
                      {step.query ? step.query : <span className={styles.placeholder}>No query provided.</span>}
                    </p>
                    <p>
                      <span className={styles.summaryLabel}>Tool:</span>{" "}
                      {step.tool ? step.tool : <span className={styles.placeholder}>Unassigned</span>}
                    </p>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      ) : (
        <div className={styles.emptyState}>
          <p>No research plan is available yet. Start a session to generate the default loop.</p>
        </div>
      )}
    </section>
  );
}
