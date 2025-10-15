"use client";

import type { DiscoveryType } from "../types";
import styles from "./DiscoveryFilter.module.css";

interface DiscoveryFilterProps {
  currentFilter: DiscoveryType | "all";
  onFilterChange: (filter: DiscoveryType | "all") => void;
  showUnviewedOnly: boolean;
  onToggleUnviewed: (show: boolean) => void;
}

const FILTER_OPTIONS: Array<{ value: DiscoveryType | "all"; label: string; icon: string }> = [
  { value: "all", label: "All Types", icon: "🔍" },
  { value: "pattern", label: "Patterns", icon: "🔗" },
  { value: "contradiction", label: "Contradictions", icon: "⚠️" },
  { value: "connection", label: "Connections", icon: "🔄" },
  { value: "gap", label: "Gaps", icon: "📊" },
  { value: "trend", label: "Trends", icon: "📈" },
  { value: "anomaly", label: "Anomalies", icon: "🎯" },
];

export function DiscoveryFilter({
  currentFilter,
  onFilterChange,
  showUnviewedOnly,
  onToggleUnviewed,
}: DiscoveryFilterProps) {
  return (
    <div className={styles.filter}>
      <div className={styles.filterGroup}>
        <label className={styles.label}>Filter by type:</label>
        <div className={styles.buttons}>
          {FILTER_OPTIONS.map((option) => (
            <button
              key={option.value}
              className={`${styles.filterButton} ${
                currentFilter === option.value ? styles.active : ""
              }`}
              onClick={() => onFilterChange(option.value)}
              aria-pressed={currentFilter === option.value}
            >
              <span className={styles.filterIcon}>{option.icon}</span>
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.toggleGroup}>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={showUnviewedOnly}
            onChange={(e) => onToggleUnviewed(e.target.checked)}
          />
          <span>New only</span>
        </label>
      </div>
    </div>
  );
}
