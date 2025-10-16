import styles from "./MetricsGrid.module.css";
import type { DashboardMetric } from "../types";

function formatDelta(delta: number | null) {
  if (delta === null || Number.isNaN(delta)) return "–";
  return `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%`;
}

function metricTrendLabel(trend: DashboardMetric["trend"]) {
  switch (trend) {
    case "up":
      return "▲";
    case "down":
      return "▼";
    default:
      return "◆";
  }
}

interface MetricsGridProps {
  metrics: DashboardMetric[];
  loading: boolean;
}

export function MetricsGrid({ metrics, loading }: MetricsGridProps) {
  return (
    <section className={styles.section} aria-busy={loading} aria-live="polite">
      <div className={styles.header}>
        <h2 className={styles.title}>Workspace metrics</h2>
        <span className={styles.caption}>
          {loading ? "Updating metrics…" : "Snapshot of your research footprint"}
        </span>
      </div>
      <div className={styles.grid}>
        {metrics.length === 0 && !loading ? (
          <p className={styles.empty}>No metrics are available yet.</p>
        ) : (
          metrics.map((metric) => (
            <article key={metric.id} className={styles.card}>
              <div className={styles.cardLabel}>{metric.label}</div>
              <div className={styles.cardValue}>
                {Intl.NumberFormat(undefined, {
                  maximumFractionDigits: 0,
                }).format(metric.value)}
                {metric.unit ? <span className={styles.unit}>{metric.unit}</span> : null}
              </div>
              <div className={styles.cardDelta}>
                <span className={`${styles.deltaBadge} ${styles[`delta-${metric.trend}`]}`}>
                  {metricTrendLabel(metric.trend)} {formatDelta(metric.delta_percentage)}
                </span>
                <span className={styles.deltaLabel}>vs. previous 7 days</span>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
