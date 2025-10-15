"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type ApiHealthStatus = "healthy" | "degraded" | "unauthenticated" | "offline";

export interface UseApiHealthOptions {
  /** Interval between background health checks in milliseconds */
  intervalMs?: number;
  /** Timeout for each request in milliseconds */
  timeoutMs?: number;
}

export interface ApiHealthSnapshot {
  status: ApiHealthStatus;
  message: string;
  isChecking: boolean;
  lastChecked: number | null;
  lastError: string | null;
  refresh: () => Promise<void>;
}

const DEFAULT_INTERVAL_MS = 30_000;
const DEFAULT_TIMEOUT_MS = 8_000;

const DEFAULT_STATE: Omit<ApiHealthSnapshot, "refresh"> = {
  status: "offline",
  message: "Checking API availability…",
  isChecking: true,
  lastChecked: null,
  lastError: null,
};

function normalizeStatus(value: string): ApiHealthStatus | null {
  const label = value.toLowerCase();
  if (["ok", "pass", "healthy", "up"].includes(label)) {
    return "healthy";
  }
  if (["warn", "warning", "degraded", "partial"].includes(label)) {
    return "degraded";
  }
  if (["unauthorized", "unauthenticated", "forbidden"].includes(label)) {
    return "unauthenticated";
  }
  if (["down", "fail", "failed", "critical", "error", "offline"].includes(label)) {
    return "offline";
  }
  return null;
}

function defaultMessageFor(status: ApiHealthStatus): string {
  switch (status) {
    case "healthy":
      return "API connection is healthy.";
    case "degraded":
      return "API is responding but reporting degraded health.";
    case "unauthenticated":
      return "Authentication is required to reach the API.";
    case "offline":
    default:
      return "Unable to reach the API.";
  }
}

function readPayloadMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const data = payload as Record<string, unknown>;
  const candidates = ["message", "detail", "description"];
  for (const key of candidates) {
    const value = data[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

function interpretSuccessPayload(payload: unknown): {
  status: ApiHealthStatus;
  message: string;
} {
  let status: ApiHealthStatus = "healthy";
  let message: string | null = null;

  if (typeof payload === "string") {
    if (payload.trim()) {
      message = payload.trim();
    }
  } else if (payload && typeof payload === "object") {
    const data = payload as Record<string, unknown>;
    if (typeof data.status === "string") {
      const normalised = normaliseStatus(data.status);
      if (normalised) {
        status = normalised;
      }
    }
    const payloadMessage = readPayloadMessage(data);
    if (payloadMessage) {
      message = payloadMessage;
    }
  }

  return {
    status,
    message: message ?? defaultMessageFor(status),
  };
}

function interpretErrorResponse(
  response: Response,
  payload: unknown,
): {
  status: ApiHealthStatus;
  message: string;
} {
  if (response.status === 401 || response.status === 403) {
    return {
      status: "unauthenticated",
      message: "Authentication is required to reach the API.",
    };
  }

  const payloadMessage = readPayloadMessage(payload);
  const fallbackMessage = payloadMessage || response.statusText || "API responded with an error.";
  const detail = `API responded with ${response.status}${response.statusText ? ` ${response.statusText}` : ""}.`;

  if (response.status >= 500 || response.status === 429) {
    return {
      status: "degraded",
      message: payloadMessage ?? detail,
    };
  }

  return {
    status: "degraded",
    message: payloadMessage ?? fallbackMessage,
  };
}

function interpretNetworkError(
  error: unknown,
  timedOut: boolean,
  timeoutMs: number,
): {
  status: ApiHealthStatus;
  message: string;
} {
  if (timedOut) {
    return {
      status: "offline",
      message: `API health check timed out after ${timeoutMs / 1000}s.`,
    };
  }

  if (error instanceof Error && error.message) {
    return {
      status: "offline",
      message: error.message,
    };
  }

  return {
    status: "offline",
    message: defaultMessageFor("offline"),
  };
}

export function useApiHealth(options: UseApiHealthOptions = {}): ApiHealthSnapshot {
  const { intervalMs = DEFAULT_INTERVAL_MS, timeoutMs = DEFAULT_TIMEOUT_MS } = options;
  const optionsRef = useRef({ intervalMs, timeoutMs });
  const controllerRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const requestIdRef = useRef(0);
  const mountedRef = useRef(true);

  const [state, setState] = useState(DEFAULT_STATE);

  useEffect(() => {
    optionsRef.current = { intervalMs, timeoutMs };
  }, [intervalMs, timeoutMs]);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort();
      controllerRef.current = null;
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const performCheck = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    setState((previous) => ({ ...previous, isChecking: true }));

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    const timeoutReason = Symbol("api-health-timeout");
    if (typeof window !== "undefined") {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = window.setTimeout(() => {
        controller.abort(timeoutReason);
      }, optionsRef.current.timeoutMs);
    }

    const clearTimeoutIfNeeded = () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };

    try {
      const response = await fetch(`/health`, {
        cache: "no-store",
        credentials: "include",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });

      let payload: unknown = null;
      const contentType = response.headers.get("content-type") ?? "";

      if (contentType.includes("application/json")) {
        try {
          payload = await response.json();
        } catch {
          payload = null;
        }
      } else {
        const text = await response.text();
        payload = text.trim() ? text : null;
      }

      if (!response.ok) {
        const { status, message } = interpretErrorResponse(response, payload);
        if (mountedRef.current && requestId === requestIdRef.current) {
          setState({
            status,
            message,
            isChecking: false,
            lastChecked: Date.now(),
            lastError: message,
          });
        }
        return;
      }

      const { status, message } = interpretSuccessPayload(payload);
      if (mountedRef.current && requestId === requestIdRef.current) {
        setState({
          status,
          message,
          isChecking: false,
          lastChecked: Date.now(),
          lastError: status === "healthy" ? null : message,
        });
      }
    } catch (error) {
      if (!mountedRef.current || requestId !== requestIdRef.current) {
        return;
      }
      const timedOut = controller.signal.reason === timeoutReason;
      const { status, message } = interpretNetworkError(
        error,
        timedOut,
        optionsRef.current.timeoutMs,
      );
      setState({
        status,
        message,
        isChecking: false,
        lastChecked: Date.now(),
        lastError: message,
      });
    } finally {
      clearTimeoutIfNeeded();
      if (controllerRef.current === controller) {
        controllerRef.current = null;
      }
    }
  }, []);

  useEffect(() => {
    void performCheck();
    if (typeof window === "undefined") {
      return () => undefined;
    }
    const poller = window.setInterval(() => {
      void performCheck();
    }, optionsRef.current.intervalMs);
    return () => {
      window.clearInterval(poller);
    };
  }, [performCheck]);

  const refresh = useCallback(async () => {
    await performCheck();
  }, [performCheck]);

  return useMemo(() => ({
    ...state,
    refresh,
  }), [state, refresh]);
}

export type { ApiHealthSnapshot as UseApiHealthSnapshot };
