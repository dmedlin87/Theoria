export interface DocumentAnnotation {
  id: string;
  document_id: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface Passage {
  id: string;
  document_id: string;
  text: string;
  osis_ref?: string | null;
  page_no?: number | null;
  t_start?: number | null;
  t_end?: number | null;
  meta?: Record<string, unknown> | null;
}

export interface DocumentDetail {
  id: string;
  title?: string | null;
  source_type?: string | null;
  collection?: string | null;
  authors?: string[] | null;
  created_at: string;
  updated_at: string;
  source_url?: string | null;
  channel?: string | null;
  video_id?: string | null;
  duration_seconds?: number | null;
  meta?: Record<string, unknown> | null;
  abstract?: string | null;
  passages: Passage[];
  annotations: DocumentAnnotation[];
}
