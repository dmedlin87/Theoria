"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import styles from "./RecentActivity.module.css";

interface Activity {
  id: string;
  type: "search" | "chat" | "upload";
  title: string;
  timestamp: string;
  href: string;
}

export function RecentActivity() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActivities();
  }, []);

  const loadActivities = async () => {
    try {
      // TODO: Replace with real API call to get user activity
      // In the future, use localStorage.getItem("recentSearches") and recentChats

      // Mock data for demonstration
      const mockActivities: Activity[] = [
        {
          id: "1",
          type: "chat",
          title: "Justification by faith discussion",
          timestamp: "2 hours ago",
          href: "/chat",
        },
        {
          id: "2",
          type: "search",
          title: "Romans 3 commentary comparison",
          timestamp: "5 hours ago",
          href: "/search?q=Romans+3+commentary",
        },
        {
          id: "3",
          type: "upload",
          title: "Uploaded: Calvin's Institutes.pdf",
          timestamp: "Yesterday",
          href: "/upload",
        },
        {
          id: "4",
          type: "search",
          title: "Covenant theology resources",
          timestamp: "2 days ago",
          href: "/search?q=covenant+theology",
        },
        {
          id: "5",
          type: "chat",
          title: "Election and predestination study",
          timestamp: "3 days ago",
          href: "/chat",
        },
      ];

      setActivities(mockActivities);
    } catch (error) {
      console.error("Error loading activities:", error);
    } finally {
      setLoading(false);
    }
  };

  const getActivityIcon = (type: Activity["type"]) => {
    switch (type) {
      case "search":
        return "🔍";
      case "chat":
        return "💬";
      case "upload":
        return "📤";
    }
  };

  const getActivityColor = (type: Activity["type"]) => {
    switch (type) {
      case "search":
        return "blue";
      case "chat":
        return "green";
      case "upload":
        return "purple";
    }
  };

  return (
    <section className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>Recent Activity</h2>
        <Link href="/research" className={styles.viewAll}>
          View all →
        </Link>
      </div>

      {loading ? (
        <div className={styles.loading}>Loading...</div>
      ) : activities.length === 0 ? (
        <div className={styles.empty}>
          <p>No recent activity</p>
          <p className={styles.emptyHint}>
            Start by searching, chatting, or uploading documents
          </p>
        </div>
      ) : (
        <div className={styles.list}>
          {activities.map((activity) => (
            <Link
              key={activity.id}
              href={activity.href}
              className={`${styles.activity} ${
                styles[`activity--${getActivityColor(activity.type)}`]
              }`}
            >
              <span className={styles.icon}>
                {getActivityIcon(activity.type)}
              </span>
              <div className={styles.content}>
                <div className={styles.activityTitle}>{activity.title}</div>
                <div className={styles.timestamp}>{activity.timestamp}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
