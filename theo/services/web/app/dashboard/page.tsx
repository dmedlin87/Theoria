"use client";

import { useState, useEffect, useMemo } from "react";
import styles from "./dashboard.module.css";
import { DiscoveryPreview } from "./components/DiscoveryPreview";
import { RecentActivity } from "./components/RecentActivity";
import { QuickStats } from "./components/QuickStats";
import { QuickActions } from "./components/QuickActions";
import { FavoriteVerses } from "./components/FavoriteVerses";

export default function DashboardPage() {
  const [userName, setUserName] = useState<string>("Researcher");
  
  // Compute time of day without useState to avoid unnecessary re-renders
  const timeOfDay = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "morning";
    else if (hour < 18) return "afternoon";
    else return "evening";
  }, []);

  useEffect(() => {
    // Get user name from localStorage if available
    const savedName = localStorage.getItem("userName");
    if (savedName) setUserName(savedName);
  }, []);

  const greeting = `Good ${timeOfDay}, ${userName}`;

  return (
    <div className={styles.dashboard}>
      <header className={styles.header}>
        <h1 className={styles.greeting}>{greeting}</h1>
        <p className={styles.tagline}>
          Your theological research workspace
        </p>
      </header>

      <div className={styles.grid}>
        {/* Left Column - Main Activity */}
        <div className={styles.mainColumn}>
          <QuickActions />
          <RecentActivity />
          <DiscoveryPreview />
        </div>

        {/* Right Column - Sidebar Widgets */}
        <div className={styles.sideColumn}>
          <QuickStats />
          <FavoriteVerses />
        </div>
      </div>
    </div>
  );
}
