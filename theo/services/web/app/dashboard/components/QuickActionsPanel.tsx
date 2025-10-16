import Link from "next/link";
import styles from "./QuickActionsPanel.module.css";
import type { DashboardQuickAction } from "../types";

interface QuickActionsPanelProps {
  actions: DashboardQuickAction[];
}

export function QuickActionsPanel({ actions }: QuickActionsPanelProps) {
  return (
    <section className={styles.section} aria-label="Quick actions">
      <h2 className={styles.title}>Jump back in</h2>
      <ul className={styles.list}>
        {actions.map((action) => (
          <li key={action.id} className={styles.listItem}>
            <Link href={action.href} className={styles.link}>
              <span className={styles.icon} aria-hidden>
                {action.icon ?? "→"}
              </span>
              <span className={styles.content}>
                <span className={styles.label}>{action.label}</span>
                {action.description ? (
                  <span className={styles.description}>{action.description}</span>
                ) : null}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
