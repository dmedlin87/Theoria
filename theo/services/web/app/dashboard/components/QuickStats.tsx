import styles from "./QuickStats.module.css";
import type { DashboardMetric } from "../types";

interface QuickStatsProps {
  metrics: DashboardMetric[];
  loading: boolean;
}

const STAT_CONFIG = [
  {
    metricId: "documents",
    label: "Documents indexed",
    icon: "📚",
  },
  {
    metricId: "notes",
    label: "Research notes",
    icon: "📝",
  },
  {
    metricId: "discoveries",
    label: "Discoveries surfaced",
    icon: "✨",
  },
  {
    metricId: "notebooks",
    label: "Active notebooks",
    icon: "📓",
  },
] as const;

function formatValue(metric: DashboardMetric | undefined, loading: boolean) {
  if (!metric) {
    return loading ? "…" : "0";
  }

  return Intl.NumberFormat(undefined, {
    maximumFractionDigits: 0,
  }).format(metric.value);
}

function formatDelta(metric: DashboardMetric | undefined) {
  if (!metric || metric.delta_percentage === null) {
    return "–";
  }

  const rounded = metric.delta_percentage.toFixed(1);
  const prefix = metric.delta_percentage > 0 ? "+" : "";
  return `${prefix}${rounded}% vs. last 7 days`;
}

export function QuickStats({ metrics, loading }: QuickStatsProps) {
  return (
    <section className={styles.section} aria-busy={loading} aria-live="polite">
      <h2 className={styles.title}>Quick stats</h2>
      <div className={styles.grid}>
        {STAT_CONFIG.map((config) => {
          const metric = metrics.find((item) => item.id === config.metricId);
          return (
            <article key={config.metricId} className={styles.stat}>
              <span className={styles.icon} aria-hidden>
                {config.icon}
              </span>
              <div className={styles.content}>
                <div className={styles.value}>{formatValue(metric, loading)}</div>
                <div className={styles.label}>{config.label}</div>
                <p className={styles.delta}>{formatDelta(metric)}</p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
