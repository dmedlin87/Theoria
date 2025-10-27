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

export type ResearchFeaturePermission = keyof ResearchFeatureFlags;
