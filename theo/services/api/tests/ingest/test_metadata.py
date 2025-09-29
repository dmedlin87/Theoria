"""Tests for metadata utilities."""

from __future__ import annotations

from theo.services.api.app.ingest.pipeline.metadata import (
    extract_guardrail_profile,
    merge_metadata,
    normalise_passage_meta,
)


def test_merge_metadata_skips_none_values() -> None:
    base = {"a": 1, "b": 2}
    overrides = {"b": None, "c": 3}
    assert merge_metadata(base, overrides) == {"a": 1, "b": 2, "c": 3}


def test_extract_guardrail_profile_from_tags() -> None:
    frontmatter = {
        "tags": ["tradition:Reformed", "domain:Soteriology"],
        "topic_domains": ["Christology"],
    }
    tradition, domains = extract_guardrail_profile(frontmatter)
    assert tradition == "Reformed"
    assert domains == ["Christology", "Soteriology"]


def test_normalise_passage_meta_combines_hints() -> None:
    class _Detected:
        primary = "John.3.16"
        all = ["John.3.16", "Ps.23.1"]

    meta = normalise_passage_meta(
        _Detected(),
        ["John.3.16", "Gen.1.1"],
        parser="plain",
        parser_version="1.0",
        chunker_version="0.1",
        chunk_index=0,
    )

    assert meta["parser"] == "plain"
    assert meta["chunk_index"] == 0
    assert "osis_refs_detected" in meta
    assert "osis_refs_hints" in meta
    assert "osis_refs_unmatched" in meta
