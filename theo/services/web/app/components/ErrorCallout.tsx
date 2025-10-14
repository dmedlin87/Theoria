"use client";

import { ReactNode, useEffect, useState } from "react";
import styles from "./ErrorCallout.module.css";

export type ErrorCalloutProps = {
  message: string;
  traceId?: string | null;
  onRetry?: () => void;
  retryLabel?: string;
  onShowDetails?: (traceId: string | null) => void;
  detailsLabel?: string;
  actions?: ReactNode;
};

export function ErrorCallout({
  message,
  traceId,
  onRetry,
  retryLabel = "Retry",
  onShowDetails,
  detailsLabel = "Details…",
  actions,
}: ErrorCalloutProps): JSX.Element {
  const normalizedTraceId = typeof traceId === "string" && traceId.trim() ? traceId.trim() : null;
  const [shouldShake, setShouldShake] = useState(true);

  useEffect(() => {
    // Reset shake animation when message changes
    setShouldShake(true);
    const timer = setTimeout(() => setShouldShake(false), 500);
    return () => clearTimeout(timer);
  }, [message]);

  return (
    <div role="alert" className={`alert alert-danger ${shouldShake ? 'shake' : ''}`.trim()}>
      <p className="alert__message">{message}</p>
      <div className={`cluster-sm ${styles.actions}`}>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn btn-sm btn-danger">
            {retryLabel}
          </button>
        )}
        {onShowDetails && (
          <button
            type="button"
            onClick={() => onShowDetails(normalizedTraceId)}
            className={`btn-ghost btn-sm ${styles.detailsButton}`}
          >
            {detailsLabel}
          </button>
        )}
        {actions}
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
