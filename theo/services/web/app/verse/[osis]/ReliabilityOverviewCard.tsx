import { getApiBaseUrl } from "../../lib/api";

type OverviewBullet = {
  summary: string;
  citations: string[];
};

type ReliabilityOverviewResponse = {
  osis: string;
  mode: string;
  consensus: OverviewBullet[];
  disputed: OverviewBullet[];
  manuscripts: OverviewBullet[];
};

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
    <section aria-label={title} style={{ display: "grid", gap: "0.5rem" }}>
      <h4 style={{ margin: "0.5rem 0 0" }}>{title}</h4>
      {items.length === 0 ? (
        <p style={{ margin: 0, color: "var(--muted-foreground, #4b5563)" }}>
          Nothing to report yet.
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.75rem" }}>
          {items.map((item, index) => (
            <li
              key={`${item.summary}-${index}`}
              style={{
                border: "1px solid var(--border, #e5e7eb)",
                borderRadius: "0.5rem",
                padding: "0.75rem",
                background: "#fff",
              }}
            >
              <p style={{ margin: 0 }}>{item.summary}</p>
              {item.citations.length > 0 ? (
                <p
                  style={{
                    margin: "0.5rem 0 0",
                    fontSize: "0.875rem",
                    color: "var(--muted-foreground, #4b5563)",
                  }}
                >
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
    overview = (await response.json()) as ReliabilityOverviewResponse;
  } catch (fetchError) {
    console.error("Failed to load reliability overview", fetchError);
    error = fetchError instanceof Error ? fetchError.message : "Unknown error";
  }

  const activeMode = mode === "skeptical" ? "Skeptical" : "Apologetic";
  const modeSummary =
    mode === "skeptical"
      ? "Skeptical mode looks for weak points and open questions."
      : "Apologetic mode highlights harmony and trusted support.";

  return (
    <div
      aria-labelledby="reliability-overview-heading"
      style={{
        background: "#f8fafc",
        borderRadius: "0.75rem",
        padding: "1.25rem",
        border: "1px solid var(--border, #e5e7eb)",
        display: "grid",
        gap: "1rem",
      }}
    >
      <header>
        <h3 id="reliability-overview-heading" style={{ margin: "0 0 0.25rem" }}>
          Reliability snapshot
        </h3>
        <p style={{ margin: 0 }}>{modeSummary}</p>
        <p style={{ margin: "0.25rem 0 0", fontSize: "0.875rem", color: "var(--muted-foreground, #4b5563)" }}>
          Mode: <strong>{activeMode}</strong>
        </p>
      </header>

      {error ? (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)", margin: 0 }}>
          Unable to load the overview. {error}
        </p>
      ) : null}

      {!error && !overview ? (
        <p style={{ margin: 0 }}>Loading reliability highlights…</p>
      ) : null}

      {overview && !error ? (
        overview.consensus.length === 0 &&
        overview.disputed.length === 0 &&
        overview.manuscripts.length === 0 ? (
          <p style={{ margin: 0 }}>
            No overview data is available yet. Add research notes to build this snapshot.
          </p>
        ) : (
          <div style={{ display: "grid", gap: "1rem" }}>
            <SectionList title="Consensus threads" items={overview.consensus} />
            <SectionList title="Disputed points" items={overview.disputed} />
            <SectionList title="Key manuscripts" items={overview.manuscripts} />
          </div>
        )
      ) : null}
    </div>
  );
}

