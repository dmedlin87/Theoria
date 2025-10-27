"use client";

import { useEffect, useMemo, useRef } from "react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./ui/tooltip";
import { useToast } from "./Toast";
import {
  type ApiHealthSnapshot,
  type ApiHealthStatus,
  useApiHealth,
} from "../lib/useApiHealth";

import styles from "./ConnectionStatusIndicator.module.css";

type ToastType = "success" | "warning" | "error" | "info";

interface BaseIndicatorProps {
  className?: string | undefined;
  /** Render the status message inline next to the badge */
  showMessage?: boolean;
  /** Visual density for the badge */
  variant?: "compact" | "inline";
  /** Whether to announce changes via toast notifications */
  announce?: boolean;
}

interface IndicatorDisplayProps extends BaseIndicatorProps {
  health: ApiHealthSnapshot;
}

const STATUS_LABELS: Record<ApiHealthStatus, string> = {
  healthy: "Connected",
  degraded: "Degraded",
  unauthenticated: "Sign-in required",
  offline: "Offline",
};

const TOAST_CONFIG: Record<ApiHealthStatus, { title: string; type: ToastType }> = {
  healthy: { title: "API connection restored", type: "success" },
  degraded: { title: "API health degraded", type: "warning" },
  unauthenticated: { title: "Authentication required", type: "error" },
  offline: { title: "API unreachable", type: "error" },
};

const STATUS_CLASS_MAP: Record<ApiHealthStatus, string> = {
  healthy: styles.statusHealthy,
  degraded: styles.statusDegraded,
  unauthenticated: styles.statusUnauthenticated,
  offline: styles.statusOffline,
};

function classNames(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

function formatTimestamp(value: number | null): string {
  if (!value) {
    return "Waiting for first check…";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Last updated just now";
  }
  return `Last updated ${date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })}`;
}

export function ConnectionStatusIndicatorDisplay({
  health,
  className,
  showMessage = false,
  variant = "compact",
  announce = true,
}: IndicatorDisplayProps): JSX.Element {
  const { addToast } = useToast();
  const previousStatusRef = useRef<ApiHealthStatus | null>(null);
  const previousMessageRef = useRef<string | null>(null);

  useEffect(() => {
    if (!announce) {
      previousStatusRef.current = health.status;
      previousMessageRef.current = health.message;
      return;
    }

    if (health.isChecking) {
      return;
    }

    const previousStatus = previousStatusRef.current;
    const previousMessage = previousMessageRef.current;
    const statusChanged = previousStatus !== health.status;
    const messageChanged = previousMessage !== health.message && health.status !== "healthy";
    const isInitial = previousStatus === null;

    if ((statusChanged || messageChanged || (isInitial && health.status !== "healthy")) && !health.isChecking) {
      const toastConfig = TOAST_CONFIG[health.status];
      addToast({ type: toastConfig.type, title: toastConfig.title, message: health.message, duration: 5000 });
    }

    previousStatusRef.current = health.status;
    previousMessageRef.current = health.message;
  }, [announce, health.status, health.message, health.isChecking, addToast]);

  const label = health.isChecking ? "Checking…" : STATUS_LABELS[health.status];
  const tooltipDescription = health.isChecking ? "Verifying API availability…" : health.message;

  const badgeClassName = useMemo(
    () =>
      classNames(styles.badgeButton, STATUS_CLASS_MAP[health.status], health.isChecking && styles.checking),
    [health.status, health.isChecking],
  );

  const wrapperClassName = classNames(styles.wrapper, variant === "inline" && styles.inlineVariant, className);

  return (
    <div
      className={wrapperClassName}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-busy={health.isChecking}
    >
      <TooltipProvider delayDuration={150}>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className={badgeClassName}
              data-status={health.status}
              aria-label={`Connection status: ${label}. ${tooltipDescription}`}
              onClick={() => {
                void health.refresh();
              }}
              disabled={health.isChecking}
            >
              <span className={styles.statusDot} aria-hidden="true" />
              <span className={styles.label}>{label}</span>
              {health.isChecking ? <span className={styles.spinner} aria-hidden="true" /> : null}
            </button>
          </TooltipTrigger>
          <TooltipContent className={styles.tooltipContent} side="bottom" align="start">
            <span>{tooltipDescription}</span>
            <span className={styles.tooltipMeta}>{formatTimestamp(health.lastChecked)}</span>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {showMessage ? <span className={styles.message}>{tooltipDescription}</span> : null}
    </div>
  );
}

export default function ConnectionStatusIndicator(props: BaseIndicatorProps): JSX.Element {
  const health = useApiHealth();
  return <ConnectionStatusIndicatorDisplay health={health} {...props} />;
}
