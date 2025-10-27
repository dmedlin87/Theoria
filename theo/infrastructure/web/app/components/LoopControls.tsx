import { memo } from "react";
import { Loader2, Pause, Play, Square, StepForward } from "lucide-react";

import type { ResearchLoopState } from "../lib/api-client";
import styles from "./LoopControls.module.css";

type LoopControlsProps = {
  state: ResearchLoopState | null;
  disabled?: boolean;
  isStreaming: boolean;
  onStop: () => void;
  onPauseToggle: () => void;
  onStep: () => void;
};

const STATUS_LABELS: Record<ResearchLoopState["status"], string> = {
  idle: "Idle",
  running: "Running",
  paused: "Paused",
  stopped: "Stopped",
  stepping: "Stepping",
  completed: "Completed",
};

function LoopControls({
  state,
  disabled = false,
  isStreaming,
  onStop,
  onPauseToggle,
  onStep,
}: LoopControlsProps): JSX.Element {
  const status = state?.status ?? "idle";
  const statusLabel = STATUS_LABELS[status];
  const isPaused = status === "paused";
  const isFinalised = status === "completed" || status === "stopped";

  const stopDisabled = disabled || !state || isFinalised;
  const pauseDisabled = disabled || !state || status === "stopped" || status === "completed";
  const stepDisabled = disabled || !state || status === "completed" || status === "stopped";

  const pauseLabel = isPaused ? "Resume" : "Pause";
  const PauseIcon = isPaused ? Play : Pause;

  const stepIndicator = state
    ? `${Math.min(state.currentStepIndex + 1, state.totalSteps)}/${state.totalSteps}`
    : null;

  return (
    <section className={styles.controls} aria-label="Loop controls">
      <div className={styles.statusBlock}>
        <span className={styles.statusLabel}>{statusLabel}</span>
        {isStreaming ? (
          <span className={styles.statusBadge}>
            <Loader2 className={styles.spinner} size={16} aria-hidden="true" />
            Streaming
          </span>
        ) : null}
        {stepIndicator ? (
          <span className={styles.stepIndicator}>Step {stepIndicator}</span>
        ) : null}
      </div>

      <div className={styles.buttonGroup}>
        <button
          type="button"
          className={styles.controlButton}
          onClick={onPauseToggle}
          disabled={pauseDisabled}
        >
          <PauseIcon size={16} aria-hidden="true" />
          <span>{pauseLabel}</span>
        </button>
        <button
          type="button"
          className={styles.controlButton}
          onClick={onStep}
          disabled={stepDisabled}
        >
          <StepForward size={16} aria-hidden="true" />
          <span>Step</span>
        </button>
        <button
          type="button"
          className={`${styles.controlButton} ${styles.stopButton}`}
          onClick={onStop}
          disabled={stopDisabled}
        >
          <Square size={16} aria-hidden="true" />
          <span>Stop</span>
        </button>
      </div>
    </section>
  );
}

export default memo(LoopControls);
