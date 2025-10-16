"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import styles from "./DiscoveryPreview.module.css";

interface Discovery {
  id: string;
  type: string;
  title: string;
  confidence: number;
  viewed?: boolean;
}

export function DiscoveryPreview() {
  const [discoveries, setDiscoveries] = useState<Discovery[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDiscoveries();
  }, []);

  const loadDiscoveries = async () => {
    try {
      const response = await fetch("/api/discoveries");
      if (!response.ok) throw new Error("Failed to load discoveries");
      const data = await response.json();
      
      // Get top 3 unviewed discoveries
      const unviewed = (data.discoveries || [])
        .filter((d: Discovery) => !d.viewed)
        .slice(0, 3);
      
      setDiscoveries(unviewed);
    } catch (error) {
      console.error("Error loading discoveries:", error);
    } finally {
      setLoading(false);
    }
  };

  const getDiscoveryIcon = (type: string) => {
    const icons: Record<string, string> = {
      pattern: "🔗",
      contradiction: "⚠️",
      gap: "📊",
      connection: "🔄",
      trend: "📈",
      anomaly: "🎯",
    };
    return icons[type] || "🔍";
  };

  const getDiscoveryColor = (type: string) => {
    const colors: Record<string, string> = {
      pattern: "blue",
      contradiction: "orange",
      gap: "purple",
      connection: "green",
      trend: "teal",
      anomaly: "red",
    };
    return colors[type] || "blue";
  };

  return (
    <section className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>🔍 New Discoveries</h2>
        <Link href="/discoveries" className={styles.viewAll}>
          View all →
        </Link>
      </div>

      {loading ? (
        <div className={styles.loading}>Analyzing your corpus...</div>
      ) : discoveries.length === 0 ? (
        <div className={styles.empty}>
          <p>No new discoveries yet</p>
          <p className={styles.emptyHint}>
            Upload documents to start finding patterns automatically
          </p>
          <Link href="/upload" className={styles.uploadButton}>
            Upload Documents →
          </Link>
        </div>
      ) : (
        <div className={styles.list}>
          {discoveries.map((discovery) => (
            <Link
              key={discovery.id}
              href="/discoveries"
              className={`${styles.discovery} ${
                styles[`discovery--${getDiscoveryColor(discovery.type)}`]
              }`}
            >
              <span className={styles.icon}>
                {getDiscoveryIcon(discovery.type)}
              </span>
              <div className={styles.content}>
                <div className={styles.discoveryTitle}>{discovery.title}</div>
                <div className={styles.meta}>
                  <span className={styles.type}>{discovery.type}</span>
                  <span className={styles.confidence}>
                    {Math.round(discovery.confidence * 100)}% confidence
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {discoveries.length > 0 && (
        <Link href="/discoveries" className={styles.viewAllButton}>
          Explore All Discoveries →
        </Link>
      )}
    </section>
  );
}
