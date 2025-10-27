"use client";

import Link from "next/link";
import { ReactNode, useCallback, useEffect, useState } from "react";
import { emitTelemetry } from "../lib/telemetry";
import styles from "./ErrorCallout.module.css";

export type ErrorCalloutProps = {
  message: string;
  traceId?: string | null;
  onRetry?: () => void;
  retryLabel?: string;
  onShowDetails?: (traceId: string | null) => void;
  detailsLabel?: string;
  actions?: ReactNode;
  helpLink?: string;
  helpLabel?: string;
  telemetry?: {
    source: string;
    page?: string;
    errorCategory?: string;
    metadata?: Record<string, unknown>;
  };
};

export function ErrorCallout({
  message,
  traceId,
  onRetry,
  retryLabel = "Retry",
  onShowDetails,
  detailsLabel = "Details…",
  actions,
  helpLink,
  helpLabel,
  telemetry,
}: ErrorCalloutProps): JSX.Element {
  const normalizedTraceId = typeof traceId === "string" && traceId.trim() ? traceId.trim() : null;
  const [shouldShake, setShouldShake] = useState(true);

  useEffect(() => {
    // Reset shake animation when message changes
    setShouldShake(true);
    const timer = setTimeout(() => setShouldShake(false), 500);
    return () => clearTimeout(timer);
  }, [message]);

  const trackAction = useCallback(
    (action: "retry" | "details" | "help") => {
      if (!telemetry) {
        return;
      }
      const metadata: Record<string, unknown> = {
        action,
        source: telemetry.source,
        has_trace_id: Boolean(normalizedTraceId),
        ...(telemetry.errorCategory ? { error_category: telemetry.errorCategory } : {}),
        ...(telemetry.metadata ?? {}),
      };
      if (normalizedTraceId) {
        metadata.trace_id = normalizedTraceId;
      }

      void emitTelemetry(
        [
          {
            event: "ui.error_callout.action",
            durationMs: 0,
            metadata,
          },
        ],
        telemetry.page ? { page: telemetry.page } : undefined,
      );
    },
    [normalizedTraceId, telemetry],
  );

  return (
    <div role="alert" className={`alert alert-danger ${shouldShake ? 'shake' : ''}`.trim()}>
      <p className="alert__message">{message}</p>
      <div className={`cluster-sm ${styles.actions}`}>
        {onRetry && (
          <button
            type="button"
            onClick={() => {
              onRetry();
              trackAction("retry");
            }}
            className="btn btn-sm btn-danger"
          >
            {retryLabel}
          </button>
        )}
        {onShowDetails && (
          <button
            type="button"
            onClick={() => {
              onShowDetails(normalizedTraceId);
              trackAction("details");
            }}
            className={`btn-ghost btn-sm ${styles.detailsButton}`}
          >
            {detailsLabel}
          </button>
        )}
        {actions}
        {helpLink && helpLabel && (
          <Link
            href={helpLink}
            className="btn-ghost btn-sm"
            onClick={() => trackAction("help")}
          >
            {helpLabel}
          </Link>
        )}
      </div>
      {normalizedTraceId && (
        <p className={`text-sm text-danger ${styles.traceInfo}`}>
          Support code: <code>{normalizedTraceId}</code>
        </p>
      )}
    </div>
  );
}

export default ErrorCallout;
