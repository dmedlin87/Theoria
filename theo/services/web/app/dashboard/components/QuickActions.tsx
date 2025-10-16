import Link from "next/link";
import styles from "./QuickActions.module.css";

export function QuickActions() {
  const actions = [
    {
      href: "/search",
      label: "Search",
      icon: "🔍",
      description: "Search your corpus",
      color: "blue",
    },
    {
      href: "/chat",
      label: "Chat",
      icon: "💬",
      description: "AI-powered research",
      color: "green",
    },
    {
      href: "/upload",
      label: "Upload",
      icon: "📤",
      description: "Add documents",
      color: "purple",
    },
    {
      href: "/discoveries?surprise=true",
      label: "Surprise Me",
      icon: "✨",
      description: "Random discovery",
      color: "orange",
    },
  ];

  return (
    <section className={styles.section}>
      <h2 className={styles.title}>Quick Actions</h2>
      <div className={styles.grid}>
        {actions.map((action) => (
          <Link
            key={action.href}
            href={action.href}
            className={`${styles.action} ${styles[`action--${action.color}`]}`}
          >
            <span className={styles.icon}>{action.icon}</span>
            <div className={styles.content}>
              <span className={styles.label}>{action.label}</span>
              <span className={styles.description}>{action.description}</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
