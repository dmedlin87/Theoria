import Link from "next/link";
import styles from "./ActivityFeed.module.css";
import type { DashboardActivity } from "../types";

interface ActivityFeedProps {
  activities: DashboardActivity[];
  loading: boolean;
}

const ICONS: Record<DashboardActivity["type"], string> = {
  document_ingested: "📚",
  note_created: "📝",
  discovery_published: "✨",
  notebook_updated: "📓",
};

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderEntry(activity: DashboardActivity) {
  const content = (
    <article className={styles.item}>
      <span className={styles.icon} aria-hidden>{ICONS[activity.type]}</span>
      <div className={styles.body}>
        <h3 className={styles.itemTitle}>{activity.title}</h3>
        {activity.description ? (
          <p className={styles.description}>{activity.description}</p>
        ) : null}
        <time className={styles.timestamp} dateTime={activity.occurred_at}>
          {formatTimestamp(activity.occurred_at)}
        </time>
      </div>
    </article>
  );

  if (activity.href) {
    return (
      <Link href={activity.href} className={styles.linkWrapper} key={activity.id}>
        {content}
      </Link>
    );
  }

  return (
    <div className={styles.linkWrapper} key={activity.id}>
      {content}
    </div>
  );
}

export function ActivityFeed({ activities, loading }: ActivityFeedProps) {
  return (
    <section className={styles.section} aria-busy={loading} aria-live="polite">
      <div className={styles.header}>
        <h2 className={styles.heading}>Recent activity</h2>
        <span className={styles.caption}>Latest updates across your workspace</span>
      </div>
      {loading && activities.length === 0 ? (
        <div className={styles.state}>Loading activity…</div>
      ) : activities.length === 0 ? (
        <div className={styles.state}>
          <p>No recent activity yet.</p>
          <p className={styles.hint}>Run a search, add a note, or explore discoveries.</p>
        </div>
      ) : (
        <div className={styles.list}>{activities.map(renderEntry)}</div>
      )}
    </section>
  );
}
