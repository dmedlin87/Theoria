"use client";

import { useState, useEffect } from "react";
import styles from "./QuickStats.module.css";

interface Stats {
  documents: number;
  verses: number;
  discoveries: number;
  sessions: number;
}

export function QuickStats() {
  const [stats, setStats] = useState<Stats>({
    documents: 0,
    verses: 0,
    discoveries: 0,
    sessions: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      // TODO: Replace with real API calls
      // For now, use mock data
      await new Promise((resolve) => setTimeout(resolve, 500));
      setStats({
        documents: 127,
        verses: 8543,
        discoveries: 12,
        sessions: 34,
      });
    } catch (error) {
      console.error("Error loading stats:", error);
    } finally {
      setLoading(false);
    }
  };

  const statItems = [
    {
      label: "Documents",
      value: stats.documents,
      icon: "📚",
      color: "blue",
    },
    {
      label: "Verses Indexed",
      value: stats.verses.toLocaleString(),
      icon: "📖",
      color: "green",
    },
    {
      label: "New Discoveries",
      value: stats.discoveries,
      icon: "🔍",
      color: "purple",
    },
    {
      label: "This Week",
      value: `${stats.sessions} sessions`,
      icon: "⚡",
      color: "orange",
    },
  ];

  return (
    <section className={styles.section}>
      <h2 className={styles.title}>Quick Stats</h2>
      <div className={styles.grid}>
        {statItems.map((item) => (
          <div key={item.label} className={styles.stat}>
            <span className={styles.icon}>{item.icon}</span>
            <div className={styles.content}>
              <div className={styles.value}>
                {loading ? "..." : item.value}
              </div>
              <div className={styles.label}>{item.label}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
