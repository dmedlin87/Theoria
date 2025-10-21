from __future__ import annotations

from pathlib import Path

from theo.services.api.app.ingest.metadata import merge_metadata


def test_merge_metadata_prefers_overrides_and_merges_nested() -> None:
    base = {
        "title": "Base",
        "nested": {"a": 1, "b": 2},
        "unchanged": "keep",
        "path": Path("/tmp/example"),
    }
    overrides = {
        "nested": {"b": 10, "c": 3},
        "unchanged": None,
        "new": ["value"],
    }

    merged = merge_metadata(base, overrides)

    assert merged["title"] == "Base"
    assert merged["nested"] == {"a": 1, "b": 10, "c": 3}
    assert merged["unchanged"] == "keep"
    assert merged["new"] == ["value"]
    assert merged["path"] == Path("/tmp/example")
