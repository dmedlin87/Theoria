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
    <div
      role="alert"
      style={{
        border: "1px solid #fecaca",
        background: "#fef2f2",
        color: "#7f1d1d",
        padding: "1rem",
        borderRadius: "0.75rem",
        display: "grid",
        gap: "0.75rem",
      }}
    >
      <p style={{ margin: 0 }}>{message}</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
        {onRetry && (
          <button type="button" onClick={onRetry}>
            {retryLabel}
          </button>
        )}
        {onShowDetails && (
          <button
            type="button"
            onClick={() => onShowDetails(normalizedTraceId)}
            style={{
              border: "none",
              background: "transparent",
              padding: 0,
              color: "#7f1d1d",
              textDecoration: "underline",
              cursor: "pointer",
            }}
          >
            {detailsLabel}
          </button>
        )}
        {actions}
      </div>
      {normalizedTraceId && (
        <p style={{ margin: 0, fontSize: "0.85rem", color: "#991b1b" }}>
          Support code: <code>{normalizedTraceId}</code>
        </p>
      )}
    </div>
  );
}

export default ErrorCallout;
