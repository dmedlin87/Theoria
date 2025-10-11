export type VerseGraphNodeKind = "verse" | "mention" | "commentary";
export type VerseGraphEdgeKind =
  | "mention"
  | "contradiction"
  | "harmony"
  | "commentary";

export interface VerseGraphNode {
  id: string;
  label: string;
  kind: VerseGraphNodeKind;
  osis?: string | null;
  data?: Record<string, unknown> | null;
}

export interface VerseGraphEdge {
  id: string;
  source: string;
  target: string;
  kind: VerseGraphEdgeKind;
  summary?: string | null;
  perspective?: string | null;
  tags?: string[] | null;
  weight?: number | null;
  source_type?: string | null;
  collection?: string | null;
  authors?: string[] | null;
  seed_id?: string | null;
  related_osis?: string | null;
  source_label?: string | null;
}

export interface VerseGraphFilters {
  perspectives: string[];
  source_types: string[];
}

export interface VerseGraphResponse {
  osis: string;
  nodes: VerseGraphNode[];
  edges: VerseGraphEdge[];
  filters: VerseGraphFilters;
}
