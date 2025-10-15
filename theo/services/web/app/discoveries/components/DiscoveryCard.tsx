"use client";

import React, { useState } from "react";
import type { Discovery } from "../types";
import styles from "./DiscoveryCard.module.css";

interface DiscoveryCardProps {
  discovery: Discovery;
  onExplore: () => void;
  onDismiss: () => void;
  onFeedback: (helpful: boolean) => void;
}

const DISCOVERY_ICONS: Record<string, string> = {
  pattern: "🔗",
  contradiction: "⚠️",
  gap: "📊",
  connection: "🔄",
  trend: "📈",
  anomaly: "🎯",
};

const DISCOVERY_COLORS: Record<string, string> = {
  pattern: "blue",
  contradiction: "orange",
  gap: "purple",
  connection: "green",
  trend: "teal",
  anomaly: "red",
};

export function DiscoveryCard({
  discovery,
  onExplore,
  onDismiss,
  onFeedback,
}: DiscoveryCardProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [isExploring, setIsExploring] = useState(false);

  const icon = DISCOVERY_ICONS[discovery.type] || "🔍";
  const color = DISCOVERY_COLORS[discovery.type] || "gray";

  const handleExplore = async () => {
    setIsExploring(true);
    await onExplore();
    // Navigate to relevant page based on discovery type
    navigateToDiscovery(discovery);
  };

  const navigateToDiscovery = (d: Discovery) => {
    // Determine where to navigate based on discovery type and metadata
    if (d.metadata.relatedVerses && d.metadata.relatedVerses.length > 0) {
      window.location.href = `/verse/${d.metadata.relatedVerses[0]}`;
    } else if (d.type === "contradiction") {
      window.location.href = "/research?mode=contradictions";
    } else if (d.metadata.relatedTopics && d.metadata.relatedTopics.length > 0 && d.metadata.relatedTopics[0]) {
      window.location.href = `/search?q=${encodeURIComponent(d.metadata.relatedTopics[0])}`;
    } else {
      window.location.href = "/search";
    }
  };

  const renderTypeSpecificDetails = () => {
    const { metadata } = discovery;

    if (metadata.patternData) {
      return (
        <div className={styles.detailsContent}>
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>Cluster Size:</span>
            <span className={styles.detailValue}>{metadata.patternData.clusterSize} documents</span>
          </div>
          {metadata.patternData.sharedThemes.length > 0 && (
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Shared Themes:</span>
              <div className={styles.tags}>
                {metadata.patternData.sharedThemes.map((theme) => (
                  <span key={theme} className={styles.tag}>
                    {theme}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    if (metadata.contradictionData) {
      return (
        <div className={styles.detailsContent}>
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>Type:</span>
            <span className={styles.detailValue}>{metadata.contradictionData.contradictionType}</span>
          </div>
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>Severity:</span>
            <span className={`${styles.severity} ${styles[metadata.contradictionData.severity]}`}>
              {metadata.contradictionData.severity}
            </span>
          </div>
        </div>
      );
    }

    if (metadata.gapData) {
      return (
        <div className={styles.detailsContent}>
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>Missing:</span>
            <span className={styles.detailValue}>{metadata.gapData.missingTopic}</span>
          </div>
          {metadata.gapData.relatedQueries.length > 0 && (
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Try searching:</span>
              <div className={styles.queries}>
                {metadata.gapData.relatedQueries.map((query) => (
                  <a
                    key={query}
                    href={`/search?q=${encodeURIComponent(query)}`}
                    className={styles.queryLink}
                  >
                    &ldquo;{query}&rdquo;
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    if (metadata.trendData) {
      return (
        <div className={styles.detailsContent}>
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>Change:</span>
            <span className={`${styles.trendValue} ${metadata.trendData.change > 0 ? styles.up : styles.down}`}>
              {metadata.trendData.change > 0 ? "↑" : "↓"} {Math.abs(metadata.trendData.change)}%
            </span>
          </div>
          <div className={styles.detailRow}>
            <span className={styles.detailLabel}>Timeframe:</span>
            <span className={styles.detailValue}>{metadata.trendData.timeframe}</span>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <article
      className={`${styles.card} ${discovery.viewed ? styles.viewed : ""}`}
      data-type={color}
    >
      {!discovery.viewed && <div className={styles.newBadge}>New</div>}
      
      <div className={styles.header}>
        <div className={styles.icon}>{icon}</div>
        <div className={styles.headerContent}>
          <h3 className={styles.title}>{discovery.title}</h3>
          <span className={styles.type}>{discovery.type}</span>
        </div>
      </div>

      <p className={styles.description}>{discovery.description}</p>

      <div className={styles.meta}>
        <div className={styles.confidence}>
          <span className={styles.confidenceLabel}>Confidence:</span>
          <div className={styles.confidenceBar}>
            <div
              className={styles.confidenceFill}
              style={{ width: `${discovery.confidence * 100}%` }}
            />
          </div>
          <span className={styles.confidenceValue}>
            {Math.round(discovery.confidence * 100)}%
          </span>
        </div>
      </div>

      {showDetails && (
        <div className={styles.details}>
          {renderTypeSpecificDetails()}
          
          {discovery.metadata.relatedDocuments && discovery.metadata.relatedDocuments.length > 0 && (
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Related Documents:</span>
              <span className={styles.detailValue}>
                {discovery.metadata.relatedDocuments.length} document(s)
              </span>
            </div>
          )}
          
          {discovery.metadata.relatedVerses && discovery.metadata.relatedVerses.length > 0 && (
            <div className={styles.detailRow}>
              <span className={styles.detailLabel}>Key Verses:</span>
              <div className={styles.verses}>
                {discovery.metadata.relatedVerses.slice(0, 5).map((verse) => (
                  <a
                    key={verse}
                    href={`/verse/${verse}`}
                    className={styles.verseLink}
                  >
                    {verse}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className={styles.actions}>
        <button
          className={styles.detailsToggle}
          onClick={() => setShowDetails(!showDetails)}
          aria-expanded={showDetails}
        >
          {showDetails ? "Hide Details ▲" : "Show Details ▼"}
        </button>
        
        <div className={styles.primaryActions}>
          <button
            className={styles.exploreButton}
            onClick={handleExplore}
            disabled={isExploring}
          >
            {isExploring ? "Loading..." : "Explore →"}
          </button>
          
          <button
            className={styles.dismissButton}
            onClick={onDismiss}
            aria-label="Dismiss discovery"
            title="Dismiss this discovery"
          >
            ✕
          </button>
        </div>
      </div>

      {!discovery.userReaction && discovery.viewed && (
        <div className={styles.feedback}>
          <span className={styles.feedbackLabel}>Was this helpful?</span>
          <button
            className={styles.feedbackButton}
            onClick={() => onFeedback(true)}
            aria-label="Mark as helpful"
          >
            👍
          </button>
          <button
            className={styles.feedbackButton}
            onClick={() => onFeedback(false)}
            aria-label="Mark as not helpful"
          >
            👎
          </button>
        </div>
      )}
    </article>
  );
}
