from theo.services.api.app.ingest.metadata import (
    extract_guardrail_profile,
    merge_metadata,
)


def test_merge_metadata_preserves_base_when_override_is_none():
    base = {"title": "Base", "author": "Alice"}
    override = {"title": None, "summary": "New"}
    merged = merge_metadata(base, override)
    assert merged["title"] == "Base"
    assert merged["summary"] == "New"


def test_extract_guardrail_profile_from_tags_and_fields():
    frontmatter = {
        "theological_tradition": "Reformed",
        "topic_domains": ["theology"],
        "tags": ["domain:biblical", "Tradition:Calvinist"],
    }
    tradition, topics = extract_guardrail_profile(frontmatter)
    assert tradition == "Reformed"
    assert topics == ["theology", "biblical"]

