import { Suspense } from "react";

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
};

interface ResearchPanelsProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default function ResearchPanels({ osis, features }: ResearchPanelsProps) {
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

  return (
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <header>
        <h2 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Research</h2>
        <p style={{ margin: 0, color: "var(--muted-foreground, #4b5563)" }}>
          Explore related findings for <strong>{osis}</strong>.
        </p>
      </header>

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
