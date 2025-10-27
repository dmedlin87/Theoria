import styles from "./ReliabilityOverviewCard.module.css";

import { getApiBaseUrl } from "../../lib/api";

type OverviewBullet = {
  summary: string;
  citations: string[];
};

type ApiOverviewBullet = {
  summary?: unknown;
  citations?: unknown;
};

type ReliabilityOverviewResponse = {
  osis: string;
  mode: string;
  consensus: OverviewBullet[];
  disputed: OverviewBullet[];
  manuscripts: OverviewBullet[];
};

type ApiReliabilityOverviewResponse = {
  osis?: string;
  mode?: string;
  consensus?: unknown;
  disputed?: unknown;
  manuscripts?: unknown;
};

function normalizeOverviewList(items: unknown): OverviewBullet[] {
  if (!Array.isArray(items)) {
    return [];
  }

  return (items as ApiOverviewBullet[])
    .filter((item) => item && typeof item === "object")
    .map((item) => ({
      summary: typeof item.summary === "string" ? item.summary : String(item.summary ?? ""),
      citations: Array.isArray(item.citations)
        ? (item.citations as unknown[]).filter((citation): citation is string => typeof citation === "string")
        : [],
    }));
}

type StudyMode = "apologetic" | "skeptical";

interface ReliabilityOverviewCardProps {
  osis: string;
  mode: StudyMode;
}

function SectionList({
  title,
  items,
}: {
  title: string;
  items: OverviewBullet[];
}) {
  return (
    <section aria-label={title} className={styles.section}>
      <h4 className={styles.sectionTitle}>{title}</h4>
      {items.length === 0 ? (
        <p className={styles.emptyState}>
          Nothing to report yet.
        </p>
      ) : (
        <ul className={styles.itemsList}>
          {items.map((item, index) => (
            <li
              key={`${item.summary}-${index}`}
              className={styles.itemCard}
            >
              <p className={styles.itemSummary}>{item.summary}</p>
              {item.citations.length > 0 ? (
                <p className={styles.itemSources}>
                  Sources: {item.citations.join(", ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default async function ReliabilityOverviewCard({
  osis,
  mode,
}: ReliabilityOverviewCardProps) {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  let overview: ReliabilityOverviewResponse | null = null;
  let error: string | null = null;

  try {
    const response = await fetch(
      `${baseUrl}/research/overview?osis=${encodeURIComponent(osis)}&mode=${mode}`,
      { cache: "no-store" },
    );
    if (!response.ok) {
      throw new Error((await response.text()) || response.statusText);
    }
    const data = (await response.json()) as ApiReliabilityOverviewResponse;

    overview = {
      osis: typeof data.osis === "string" ? data.osis : osis,
      mode: typeof data.mode === "string" ? data.mode : mode,
      consensus: normalizeOverviewList(data.consensus),
      disputed: normalizeOverviewList(data.disputed),
      manuscripts: normalizeOverviewList(data.manuscripts),
    } satisfies ReliabilityOverviewResponse;
  } catch (fetchError) {
    console.error("Failed to load reliability overview", fetchError);
    error = fetchError instanceof Error ? fetchError.message : "Unknown error";
  }

  const activeMode = mode === "skeptical" ? "Skeptical" : "Apologetic";
  const modeSummary =
    mode === "skeptical"
      ? "Skeptical mode looks for weak points and open questions."
      : "Apologetic mode highlights harmony and trusted support.";

  const consensusItems = overview?.consensus ?? [];
  const disputedItems = overview?.disputed ?? [];
  const manuscriptItems = overview?.manuscripts ?? [];
  const hasOverviewContent =
    consensusItems.length > 0 || disputedItems.length > 0 || manuscriptItems.length > 0;

  return (
    <div
      aria-labelledby="reliability-overview-heading"
      className={styles.card}
    >
      <header>
        <h3 id="reliability-overview-heading" className={styles.heading}>
          Reliability snapshot
        </h3>
        <p className={styles.description}>{modeSummary}</p>
        <p className={styles.modeLabel}>
          Mode: <strong>{activeMode}</strong>
        </p>
      </header>

      {error ? (
        <p role="alert" className={styles.errorMessage}>
          Unable to load the overview. {error}
        </p>
      ) : null}

      {!error && !overview ? (
        <p className={styles.loadingMessage}>Loading reliability highlights…</p>
      ) : null}

      {overview && !error ? (
        !hasOverviewContent ? (
          <p className={styles.emptyMessage}>
            No overview data is available yet. Add research notes to build this snapshot.
          </p>
        ) : (
          <div className={styles.sectionsContainer}>
            <SectionList title="Consensus threads" items={consensusItems} />
            <SectionList title="Disputed points" items={disputedItems} />
            <SectionList title="Key manuscripts" items={manuscriptItems} />
          </div>
        )
      ) : null}
    </div>
  );
}

