import { getApiBaseUrl } from "../lib/api";
import { DashboardClient } from "./DashboardClient";
import type { DashboardSummary } from "./types";

export const revalidate = 0;

async function loadInitialDashboard(): Promise<DashboardSummary | null> {
  const url = `${getApiBaseUrl()}/dashboard`;
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as DashboardSummary;
  } catch (error) {
    console.error("Failed to prefetch dashboard data", error);
    return null;
  }
}

export default async function DashboardScreen() {
  const initialData = await loadInitialDashboard();
  return <DashboardClient initialData={initialData} />;
}
