export type MetricTrend = "up" | "down" | "flat";

export interface DashboardMetric {
  id: string;
  label: string;
  value: number;
  unit: string | null;
  delta_percentage: number | null;
  trend: MetricTrend;
}

export interface DashboardActivity {
  id: string;
  type:
    | "document_ingested"
    | "note_created"
    | "discovery_published"
    | "notebook_updated";
  title: string;
  description: string | null;
  occurred_at: string;
  href: string | null;
}

export interface DashboardQuickAction {
  id: string;
  label: string;
  href: string;
  description: string | null;
  icon: string | null;
}

export interface DashboardUserSummary {
  name: string;
  plan: string | null;
  timezone: string | null;
  last_login: string | null;
}

export interface DashboardSummary {
  generated_at: string;
  user: DashboardUserSummary;
  metrics: DashboardMetric[];
  activity: DashboardActivity[];
  quick_actions: DashboardQuickAction[];
}
