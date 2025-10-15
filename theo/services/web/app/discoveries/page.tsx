"use client";

import { useState, useEffect } from "react";
import styles from "./discoveries.module.css";
import { DiscoveryCard } from "./components/DiscoveryCard";
import { DiscoveryFilter } from "./components/DiscoveryFilter";
import type { Discovery, DiscoveryType } from "./types";

export default function DiscoveriesPage() {
  const [discoveries, setDiscoveries] = useState<Discovery[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<DiscoveryType | "all">("all");
  const [viewedOnly, setViewedOnly] = useState(false);

  useEffect(() => {
    loadDiscoveries();
  }, []);

  const loadDiscoveries = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/discoveries");
      if (!response.ok) throw new Error("Failed to load discoveries");
      const data = await response.json();
      setDiscoveries(data.discoveries || []);
    } catch (error) {
      console.error("Error loading discoveries:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleExplore = async (discoveryId: string) => {
    // Mark as viewed
    try {
      await fetch(`/api/discoveries/${discoveryId}/view`, { method: "POST" });
      setDiscoveries((prev) =>
        prev.map((d) => (d.id === discoveryId ? { ...d, viewed: true } : d))
      );
    } catch (error) {
      console.error("Error marking discovery as viewed:", error);
    }
  };

  const handleDismiss = async (discoveryId: string) => {
    try {
      await fetch(`/api/discoveries/${discoveryId}`, { method: "DELETE" });
      setDiscoveries((prev) => prev.filter((d) => d.id !== discoveryId));
    } catch (error) {
      console.error("Error dismissing discovery:", error);
    }
  };

  const handleFeedback = async (discoveryId: string, helpful: boolean) => {
    try {
      await fetch(`/api/discoveries/${discoveryId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ helpful }),
      });
      setDiscoveries((prev) =>
        prev.map((d) =>
          d.id === discoveryId
            ? { ...d, userReaction: helpful ? "helpful" : "not_helpful" }
            : d
        )
      );
    } catch (error) {
      console.error("Error submitting feedback:", error);
    }
  };

  const filteredDiscoveries = discoveries
    .filter((d) => filter === "all" || d.type === filter)
    .filter((d) => !viewedOnly || !d.viewed);

  const stats = {
    total: discoveries.length,
    unviewed: discoveries.filter((d) => !d.viewed).length,
    patterns: discoveries.filter((d) => d.type === "pattern").length,
    contradictions: discoveries.filter((d) => d.type === "contradiction").length,
    gaps: discoveries.filter((d) => d.type === "gap").length,
    connections: discoveries.filter((d) => d.type === "connection").length,
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerContent}>
          <h1>🔍 Discoveries</h1>
          <p className={styles.subtitle}>
            Auto-detected insights, patterns, and connections from your research corpus
          </p>
        </div>
        
        <div className={styles.stats}>
          <div className={styles.statCard}>
            <span className={styles.statValue}>{stats.unviewed}</span>
            <span className={styles.statLabel}>New</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statValue}>{stats.patterns}</span>
            <span className={styles.statLabel}>Patterns</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statValue}>{stats.contradictions}</span>
            <span className={styles.statLabel}>Contradictions</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statValue}>{stats.connections}</span>
            <span className={styles.statLabel}>Connections</span>
          </div>
        </div>
      </header>

      <div className={styles.toolbar}>
        <DiscoveryFilter
          currentFilter={filter}
          onFilterChange={setFilter}
          showUnviewedOnly={viewedOnly}
          onToggleUnviewed={setViewedOnly}
        />
        
        <button
          className={styles.refreshButton}
          onClick={loadDiscoveries}
          disabled={loading}
          aria-label="Refresh discoveries"
        >
          {loading ? "⟳ Analyzing..." : "↻ Refresh"}
        </button>
      </div>

      <main className={styles.content}>
        {loading && discoveries.length === 0 ? (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <p>Analyzing your corpus...</p>
          </div>
        ) : filteredDiscoveries.length === 0 ? (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>🔍</div>
            <h2>No discoveries yet</h2>
            <p>
              {viewedOnly
                ? "You've viewed all discoveries! Uncheck 'New only' to see everything."
                : discoveries.length === 0
                ? "Upload some documents and we'll start finding patterns automatically."
                : "Try adjusting your filters to see more discoveries."}
            </p>
            {discoveries.length === 0 && (
              <a href="/upload" className={styles.uploadLink}>
                Upload Documents →
              </a>
            )}
          </div>
        ) : (
          <div className={styles.grid}>
            {filteredDiscoveries.map((discovery) => (
              <DiscoveryCard
                key={discovery.id}
                discovery={discovery}
                onExplore={() => handleExplore(discovery.id)}
                onDismiss={() => handleDismiss(discovery.id)}
                onFeedback={(helpful) => handleFeedback(discovery.id, helpful)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
