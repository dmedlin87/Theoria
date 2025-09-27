import { Suspense } from "react";

import { getApiBaseUrl } from "../../lib/api";
import {
  DeadSeaScrollsChip,
  type DeadSeaScrollLink,
} from "./DeadSeaScrollsChip";

import ContradictionsPanel from "./ContradictionsPanel";
import CommentariesPanel from "./CommentariesPanel";
import CrossReferencesPanel from "./CrossReferencesPanel";
import GeoPanel from "./GeoPanel";
import MorphologyPanel from "./MorphologyPanel";
import TextualVariantsPanel from "./TextualVariantsPanel";

export type ResearchFeatureFlags = {
  research?: boolean;
  contradictions?: boolean;
  geo?: boolean;
  cross_references?: boolean;
  textual_variants?: boolean;
  morphology?: boolean;
  commentaries?: boolean;
  verse_timeline?: boolean;
  dss_linkages?: boolean;
};

interface ResearchPanelsProps {
  osis: string;
  features: ResearchFeatureFlags;
}

async function fetchDeadSeaScrollLinks(osis: string): Promise<DeadSeaScrollLink[]> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const response = await fetch(
    `${baseUrl}/research/dss?osis=${encodeURIComponent(osis)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error((await response.text()) || response.statusText);
  }
  const payload = (await response.json()) as {
    links?: DeadSeaScrollLink[] | null;
  };
  return Array.isArray(payload.links)
    ? payload.links.filter((link): link is DeadSeaScrollLink => Boolean(link?.id))
    : [];
}

export default async function ResearchPanels({
  osis,
  features,
}: ResearchPanelsProps) {
  if (!features?.research) {
    return null;
  }

  const hasAnyPanel = Boolean(
    features.contradictions ||
      features.cross_references ||
      features.textual_variants ||
      features.morphology ||
      features.commentaries ||
      features.geo,
  );

  let dssLinks: DeadSeaScrollLink[] = [];
  let dssError: string | null = null;
  if (features.dss_linkages) {
    try {
      dssLinks = await fetchDeadSeaScrollLinks(osis);
    } catch (error) {
      console.error("Failed to load DSS linkages", error);
      dssError = error instanceof Error ? error.message : "Unknown error";
    }
  }

  return (
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <header>
        <h2 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Research</h2>
        <p style={{ margin: 0, color: "var(--muted-foreground, #4b5563)" }}>
          Explore related findings for <strong>{osis}</strong>.
        </p>
      </header>

      {features.dss_linkages ? (
        <div>
          <DeadSeaScrollsChip links={dssLinks} />
          {dssError ? (
            <p role="alert" style={{ color: "var(--danger, #b91c1c)" }}>
              Unable to load Dead Sea Scrolls links. {dssError}
            </p>
          ) : null}
        </div>
      ) : null}

      {features.contradictions ? (
        <Suspense fallback={<p>Loading contradictions research…</p>}>
          <ContradictionsPanel osis={osis} features={features} />
        </Suspense>
      ) : null}

      {features.cross_references ? (
        <Suspense fallback={<p>Loading cross-references…</p>}>
          <CrossReferencesPanel osis={osis} features={features} />
        </Suspense>
      ) : null}

      {features.textual_variants ? (
        <Suspense fallback={<p>Loading textual variants…</p>}>
          <TextualVariantsPanel osis={osis} features={features} />
        </Suspense>
      ) : null}

      {features.morphology ? (
        <Suspense fallback={<p>Loading morphology…</p>}>
          <MorphologyPanel osis={osis} features={features} />
        </Suspense>
      ) : null}

      {features.commentaries ? (
        <Suspense fallback={<p>Loading commentaries…</p>}>
          <CommentariesPanel osis={osis} features={features} />
        </Suspense>
      ) : null}

      {features.geo ? <GeoPanel osis={osis} features={features} /> : null}

      {!hasAnyPanel && (
        <p style={{ color: "var(--muted-foreground, #4b5563)" }}>
          No research panels are available for this verse yet.
        </p>
      )}
    </div>
  );
}
