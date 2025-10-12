"use client";

import { ReactNode } from "react";

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

  return (
    <div role="alert" className="alert alert-danger">
      <p className="alert__message">{message}</p>
      <div className="cluster-sm" style={{ alignItems: "center" }}>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn btn-sm btn-danger">
            {retryLabel}
          </button>
        )}
        {onShowDetails && (
          <button
            type="button"
            onClick={() => onShowDetails(normalizedTraceId)}
            className="btn-ghost btn-sm"
            style={{ color: "var(--color-danger)" }}
          >
            {detailsLabel}
          </button>
        )}
        {actions}
      </div>
      {normalizedTraceId && (
        <p className="text-sm text-danger" style={{ margin: 0 }}>
          Support code: <code>{normalizedTraceId}</code>
        </p>
      )}
    </div>
  );
}

export default ErrorCallout;
