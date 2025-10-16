import styles from "./ProfileSummary.module.css";
import type { DashboardUserSummary } from "../types";

interface ProfileSummaryProps {
  user: DashboardUserSummary | null;
}

function formatLastLogin(lastLogin: string | null) {
  if (!lastLogin) return "Sign in to personalise";
  const date = new Date(lastLogin);
  if (Number.isNaN(date.getTime())) return "Active recently";
  return `Last active ${date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })}`;
}

export function ProfileSummary({ user }: ProfileSummaryProps) {
  const plan = user?.plan ?? "Research plan";
  const timezone = user?.timezone ?? "Local timezone";

  return (
    <section className={styles.section} aria-label="Profile summary">
      <h2 className={styles.title}>Your workspace</h2>
      <div className={styles.details}>
        <div>
          <div className={styles.label}>Collaborator</div>
          <div className={styles.value}>{user?.name ?? "Researcher"}</div>
        </div>
        <div>
          <div className={styles.label}>Plan</div>
          <div className={styles.value}>{plan}</div>
        </div>
        <div>
          <div className={styles.label}>Timezone</div>
          <div className={styles.value}>{timezone}</div>
        </div>
      </div>
      <p className={styles.subtle}>{formatLastLogin(user?.last_login ?? null)}</p>
    </section>
  );
}
