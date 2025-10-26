> **Archived on 2025-10-26**

# Frontmatter Conventions

Theoria optionally reads YAML or JSON frontmatter blocks to enrich metadata
and deduplicate documents.

## Supported Keys

- `title`: Canonical document title.
- `author`: Author or organization.
- `date`: ISO8601 publication date.
- `tags`: List of topical tags.
- `osis_refs`: Hint references used during seeding.

## Storage

Frontmatter is persisted alongside raw files in
`$STORAGE_ROOT/{document_id}/frontmatter.json`.
