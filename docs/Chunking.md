# Chunking Strategy

Theo Engine distinguishes between paginated sources (PDF, DOCX) and temporal
sources (audio, video transcripts). Chunking must preserve citation anchors and
minimize verse boundary splits.

## Paginated Sources

- Extract per-page text while retaining page numbers.
- Further split on headings or paragraphs if pages exceed embedding token limits.

## Temporal Sources

- Use transcript timestamps to create ~30 second windows.
- Merge adjacent segments when a verse spans multiple timestamps.

## Markdown Notes

- Respect YAML frontmatter for metadata.
- Split on top-level headings (`# Heading`).

## TEI Pipeline

- The `tei_pipeline` module orchestrates OCR/HTR ingestion for scanned corpora.
- OCR confidences are averaged per chunk and persisted on each passage's `meta`.
- TEI markup (speakers, people, places, scripture refs) is generated alongside
  chunked text so downstream retrieval can reason over structured metadata.
