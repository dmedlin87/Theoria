"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import styles from "./SystemHealthCard.module.css";

type AdapterStatus = "healthy" | "degraded" | "unavailable";

interface AdapterDetail {
  name: string;
  status: AdapterStatus;
  message: string | null;
  latencyMs: number | null;
}

interface HealthDetailResponse {
  status?: string;
  message?: string;
  checked_at?: string;
  adapters?: Array<{
    name?: string;
    status?: string;
    message?: string | null;
    latency_ms?: number | null;
  }>;
}

const STATUS_LABELS: Record<AdapterStatus, string> = {
  healthy: "Operational",
  degraded: "Degraded",
  unavailable: "Unavailable",
};

const STATUS_CLASS_MAP: Record<AdapterStatus, string> = {
  healthy: styles.statusHealthy,
  degraded: styles.statusDegraded,
  unavailable: styles.statusUnavailable,
};

const ADAPTER_STATUS_CLASS: Record<AdapterStatus, string> = {
  healthy: styles.adapterStatusHealthy,
  degraded: styles.adapterStatusDegraded,
  unavailable: styles.adapterStatusUnavailable,
};

const REFRESH_INTERVAL_MS = 60_000;

function classNames(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

function normaliseStatus(value: string | undefined): AdapterStatus {
  if (!value) {
    return "degraded";
  }
  const label = value.toLowerCase();
  if (["ok", "healthy", "pass", "up"].includes(label)) {
    return "healthy";
  }
  if (["warn", "warning", "degraded", "partial"].includes(label)) {
    return "degraded";
  }
  return "unavailable";
}

function defaultMessageFor(status: AdapterStatus): string {
  switch (status) {
    case "healthy":
      return "All systems operational.";
    case "degraded":
      return "One or more adapters are reporting degraded health.";
    case "unavailable":
    default:
      return "System health data is currently unavailable.";
  }
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "Awaiting first health check…";
  }
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return "Updated just now";
  }
  return `Checked ${timestamp.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })}`;
}

function formatLatency(latency: number | null): string | null {
  if (latency === null || typeof latency !== "number" || Number.isNaN(latency)) {
    return null;
  }
  const precision = latency >= 100 ? 0 : 1;
  return `${latency.toFixed(precision)} ms`;
}

function normaliseAdapters(payload: HealthDetailResponse | null): AdapterDetail[] {
  if (!payload?.adapters || !Array.isArray(payload.adapters)) {
    return [];
  }
  return payload.adapters
    .map((adapter) => ({
      name: (adapter.name ?? "adapter").replace(/[_\-]/g, " "),
      status: normaliseStatus(adapter.status),
      message: adapter.message ?? null,
      latencyMs:
        typeof adapter.latency_ms === "number" && !Number.isNaN(adapter.latency_ms)
          ? adapter.latency_ms
          : null,
    }))
    .sort((left, right) => left.name.localeCompare(right.name));
}

export function SystemHealthCard(): JSX.Element {
  const controllerRef = useRef<AbortController | null>(null);
  const hasLoadedRef = useRef(false);

  const [adapters, setAdapters] = useState<AdapterDetail[]>([]);
  const [status, setStatus] = useState<AdapterStatus>("healthy");
  const [message, setMessage] = useState<string>(defaultMessageFor("healthy"));
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      if (!hasLoadedRef.current) {
        setLoading(true);
      }

      try {
        const response = await fetch("/health/detail", {
          cache: "no-store",
          credentials: "include",
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });

        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || `Health check failed with ${response.status}`);
        }

        const payload = (await response.json()) as HealthDetailResponse;
        if (cancelled || controller.signal.aborted) {
          return;
        }

        const normalisedStatus = normaliseStatus(payload.status);
        setStatus(normalisedStatus);
        setMessage(payload.message?.trim() || defaultMessageFor(normalisedStatus));
        setAdapters(normaliseAdapters(payload));
        setCheckedAt(payload.checked_at ?? new Date().toISOString());
        setError(null);
        setLoading(false);
        hasLoadedRef.current = true;
      } catch (rawError) {
        if (controller.signal.aborted || cancelled) {
          return;
        }

        const errorMessage =
          rawError instanceof Error && rawError.message
            ? rawError.message
            : "Unable to load system health.";
        setError(errorMessage);
        setStatus("unavailable");
        setMessage(errorMessage);
        setLoading(false);
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
        }
      }
    };

    void load();
    const interval = window.setInterval(() => {
      void load();
    }, REFRESH_INTERVAL_MS);

    return () => {
      cancelled = true;
      controllerRef.current?.abort();
      controllerRef.current = null;
      window.clearInterval(interval);
    };
  }, []);

  const badgeClassName = useMemo(
    () => classNames(styles.statusBadge, STATUS_CLASS_MAP[status]),
    [status],
  );

  const footerText = useMemo(() => formatTimestamp(checkedAt), [checkedAt]);

  return (
    <section className={styles.card} aria-live="polite" aria-busy={loading}>
      <div className={styles.header}>
        <h2 className={styles.title}>System health</h2>
        <span className={badgeClassName} data-status={status}>
          {STATUS_LABELS[status]}
        </span>
      </div>
      <p className={classNames(styles.summary, loading && styles.loading, error && styles.error)}>
        {loading ? "Loading health status…" : message}
      </p>
      {adapters.length > 0 ? (
        <ul className={styles.adapters}>
          {adapters.map((adapter) => (
            <li key={adapter.name} className={styles.adapterItem}>
              <span
                className={classNames(
                  styles.adapterStatusDot,
                  ADAPTER_STATUS_CLASS[adapter.status],
                )}
                aria-hidden="true"
              />
              <div className={styles.adapterContent}>
                <span className={styles.adapterName}>{adapter.name}</span>
                <p className={styles.adapterMessage}>
                  {adapter.message ?? defaultMessageFor(adapter.status)}
                </p>
                {formatLatency(adapter.latencyMs) ? (
                  <span className={styles.adapterMeta}>
                    Response time {formatLatency(adapter.latencyMs)}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      <footer className={styles.footer}>{footerText}</footer>
    </section>
  );
}

export default SystemHealthCard;
