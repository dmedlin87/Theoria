"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getApiBaseUrl } from "../lib/api";
import styles from "./dashboard.module.css";
import { ActivityFeed } from "./components/ActivityFeed";
import { MetricsGrid } from "./components/MetricsGrid";
import { ProfileSummary } from "./components/ProfileSummary";
import { QuickActionsPanel } from "./components/QuickActionsPanel";
import type { DashboardSummary } from "./types";

interface DashboardClientProps {
  initialData: DashboardSummary | null;
}

type Status = "idle" | "loading" | "success" | "error";

async function requestDashboardSummary(signal?: AbortSignal): Promise<DashboardSummary> {
  const response = await fetch(`${getApiBaseUrl()}/dashboard`, {
    cache: "no-store",
    credentials: "include",
    signal,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return (await response.json()) as DashboardSummary;
}

export function DashboardClient({ initialData }: DashboardClientProps) {
  const [data, setData] = useState<DashboardSummary | null>(initialData);
  const [status, setStatus] = useState<Status>(() => (initialData ? "success" : "idle"));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(initialData);
    setStatus(initialData ? "success" : "idle");
  }, [initialData]);

  const loadDashboard = useCallback(async (signal?: AbortSignal) => {
    setStatus("loading");
    setError(null);

    try {
      const summary = await requestDashboardSummary(signal);
      setData(summary);
      setStatus("success");
    } catch (loadError) {
      if ((loadError as Error).name === "AbortError") {
        return;
      }
      console.error("Failed to load dashboard", loadError);
      setError(loadError instanceof Error ? loadError.message : "Unknown error");
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    if (!initialData) {
      const controller = new AbortController();
      void loadDashboard(controller.signal);
      return () => controller.abort();
    }
  }, [initialData, loadDashboard]);

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  }, []);

  const lastUpdated = data ? new Date(data.generated_at) : null;
  const statusMessage = useMemo(() => {
    if (status === "loading") {
      return { className: styles.statusLoading, text: "Refreshing dashboard…" };
    }
    if (status === "error") {
      return {
        className: styles.statusError,
        text: error ? `Unable to refresh dashboard: ${error}` : "Unable to refresh dashboard",
      };
    }
    return null;
  }, [status, error]);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.titleGroup}>
          <p className={styles.greeting}>
            {greeting}, {data?.user.name ?? "Researcher"}
          </p>
          <h1 className={styles.headline}>Your personalised research console</h1>
          <p className={styles.subheadline}>
            Track progress across ingest, study notes, and AI surfaced discoveries.
          </p>
        </div>
        <div className={styles.meta}>
          {lastUpdated ? (
            <span className={styles.timestamp}>
              Updated {lastUpdated.toLocaleString(undefined, { hour: "numeric", minute: "2-digit" })}
            </span>
          ) : (
            <span className={styles.timestamp}>Waiting for first update…</span>
          )}
          <div className={styles.actions}>
            <button type="button" className={styles.refreshButton} onClick={() => void loadDashboard()}>
              Refresh data
            </button>
          </div>
        </div>
      </header>

      <div className={styles.statusRow}>
        {statusMessage ? (
          <span className={`${styles.statusMessage} ${statusMessage.className}`} role={status === "error" ? "alert" : "status"}>
            {statusMessage.text}
            {status === "error" ? (
              <button type="button" className={styles.retryButton} onClick={() => void loadDashboard()}>
                Try again
              </button>
            ) : null}
          </span>
        ) : null}
      </div>

      <div className={styles.grid}>
        <div className={styles.mainColumn}>
          <MetricsGrid metrics={data?.metrics ?? []} loading={status === "loading" && !data} />
          <ActivityFeed activities={data?.activity ?? []} loading={status === "loading" && !data} />
        </div>
        <div className={styles.sideColumn}>
          <ProfileSummary user={data?.user ?? null} />
          <QuickActionsPanel actions={data?.quick_actions ?? []} />
        </div>
      </div>
    </div>
  );
}
