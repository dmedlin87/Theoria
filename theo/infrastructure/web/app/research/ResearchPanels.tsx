"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import styles from "./ResearchPanels.module.css";

import ModeChangeBanner from "../components/ModeChangeBanner";
import { formatEmphasisSummary } from "../mode-config";
import { useMode } from "../mode-context";
import ContradictionsPanel from "./panels/ContradictionsPanel";
import CommentariesPanel from "./panels/CommentariesPanel";
import CrossReferencesPanel from "./panels/CrossReferencesPanel";
import MorphologyPanel from "./panels/MorphologyPanel";
import TextualVariantsPanel from "./panels/TextualVariantsPanel";
import type { ResearchFeatureFlags } from "./types";

const GeoPanel = dynamic(() => import("./panels/GeoPanel"), {
  loading: () => <GeoPanelSkeleton />,
  ssr: false,
});

function GeoPanelSkeleton(): JSX.Element {
  return (
    <section aria-busy="true" className="geo-panel-skeleton">
      <div className="skeleton geo-panel-skeleton__title" />
      <div className="skeleton geo-panel-skeleton__subtitle" />
      <div className="skeleton geo-panel-skeleton__map" />
    </section>
  );
}

interface ResearchPanelsProps {
  osis: string;
  features: ResearchFeatureFlags;
}

export default function ResearchPanels({ osis, features }: ResearchPanelsProps) {
  const { mode } = useMode();
  const modeSummary = useMemo(() => formatEmphasisSummary(mode), [mode]);

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
    <div className={styles.container}>
      <header>
        <h2 className={styles.heading}>Research</h2>
        <p className={styles.description}>
          Explore related findings for <strong>{osis}</strong> in{" "}
          <strong>{mode.label}</strong> mode.
        </p>
        <p className={styles.modeSummary}>
          {modeSummary}
        </p>
        <p className={styles.helpText}>
          Prefer chatting? Open these panels inline from the Copilot workspace with the <code>/research</code> command.
        </p>
        <ModeChangeBanner area="Research panels" />
      </header>

      {features.contradictions ? (
        <ContradictionsPanel osis={osis} features={features} />
      ) : null}

      {features.cross_references ? (
        <CrossReferencesPanel osis={osis} features={features} />
      ) : null}

      {features.textual_variants ? (
        <TextualVariantsPanel osis={osis} features={features} />
      ) : null}

      {features.morphology ? <MorphologyPanel osis={osis} features={features} /> : null}

      {features.commentaries ? (
        <CommentariesPanel osis={osis} features={features} />
      ) : null}

      {features.geo ? <GeoPanel osis={osis} features={features} /> : null}

      {!hasAnyPanel && (
        <p className={styles.emptyMessage}>
          No research panels are available for this verse yet.
        </p>
      )}
    </div>
  );
}
