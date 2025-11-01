---
title: Theo Export export-fixture
schema_version: 2024-07-01
created_at: 2024-01-01T00:00:00+00:00
export_type: documents
record_count: 1
---

## Manifest
```json
{
  "export_id": "export-fixture",
  "schema_version": "2024-07-01",
  "created_at": "2024-01-01T00:00:00Z",
  "type": "documents",
  "filters": {
    "collection": "theology",
    "author": null,
    "source_type": null
  },
  "totals": {
    "documents": 1,
    "passages": 1,
    "returned": 1
  },
  "app_git_sha": "abc1234",
  "enrichment_version": 2,
  "cursor": "doc-1",
  "next_cursor": null,
  "mode": null
}
```

## Records
```json
[
  {
    "kind": "document",
    "document_id": "doc-1",
    "title": "Example Document",
    "collection": "theology",
    "source_type": "article",
    "authors": [
      "Jane Doe",
      "John Roe"
    ],
    "doi": "10.1234/example",
    "venue": "TheoConf",
    "year": 2023,
    "topics": [
      "grace"
    ],
    "primary_topic": "Grace",
    "enrichment_version": 2,
    "provenance_score": 82,
    "abstract": "An example abstract",
    "source_url": "https://example.com/doc-1",
    "metadata": {
      "publisher": "Theo Press",
      "pages": "10-12"
    },
    "passages": [
      {
        "id": "passage-1",
        "document_id": "doc-1",
        "osis_ref": "John.1.1",
        "page_no": 1,
        "t_start": null,
        "t_end": null,
        "text": "In the beginning was the Word.",
        "meta": {
          "snippet": "In the beginning was the Word."
        }
      }
    ]
  }
]
```

%% Theo export provenance manifest embedded above %%
