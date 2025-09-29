"use client";

import { useMemo } from "react";

import ModeChangeBanner from "../components/ModeChangeBanner";
import { formatEmphasisSummary } from "../mode-config";
import { useMode } from "../mode-context";
import ContradictionsPanel from "./panels/ContradictionsPanel";
import CommentariesPanel from "./panels/CommentariesPanel";
import CrossReferencesPanel from "./panels/CrossReferencesPanel";
import GeoPanel from "./panels/GeoPanel";
import MorphologyPanel from "./panels/MorphologyPanel";
import TextualVariantsPanel from "./panels/TextualVariantsPanel";
import type { ResearchFeatureFlags } from "./types";

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
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <header>
        <h2 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Research</h2>
        <p style={{ margin: 0, color: "var(--muted-foreground, #4b5563)" }}>
          Explore related findings for <strong>{osis}</strong> in{" "}
          <strong>{mode.label}</strong> mode.
        </p>
        <p style={{ margin: "0.5rem 0 0", color: "var(--muted-foreground, #64748b)" }}>
          {modeSummary}
        </p>
        <p style={{ margin: "0.5rem 0 0", color: "var(--muted-foreground, #64748b)", fontSize: "0.9rem" }}>
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
        <p style={{ color: "var(--muted-foreground, #4b5563)" }}>
          No research panels are available for this verse yet.
        </p>
      )}
    </div>
  );
}
