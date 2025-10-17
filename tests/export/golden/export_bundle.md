---
title: Theo Export export-fixture
schema_version: 2024-07-01
created_at: 2024-01-01T00:00:00+00:00
export_type: search
record_count: 1
---

## Manifest
```json
{
  "export_id": "export-fixture",
  "schema_version": "2024-07-01",
  "created_at": "2024-01-01T00:00:00Z",
  "type": "search",
  "filters": {
    "query": "grace"
  },
  "totals": {
    "results": 1,
    "returned": 1
  },
  "app_git_sha": "abc1234",
  "enrichment_version": 2,
  "cursor": "passage-1",
  "next_cursor": null,
  "mode": "results"
}
```

## Records
```json
[
  {
    "kind": "result",
    "rank": 1,
    "score": 0.87,
    "document_id": "doc-1",
    "title": "Example Document",
    "snippet": "Example snippet"
  }
]
```

%% Theo export provenance manifest embedded above %%
