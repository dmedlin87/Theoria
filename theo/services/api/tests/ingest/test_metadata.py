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


def test_repro_merge_metadata_nested_dict_preserves_base_keys():
    base = {"speakers": {"primary": "Alice", "secondary": "Bob"}}
    overrides = {"speakers": {"secondary": "Carol"}}

    merged = merge_metadata(base, overrides)

    # Expect nested dictionaries to be merged rather than overwritten so the
    # untouched "primary" speaker is preserved.
    assert merged["speakers"]["primary"] == "Alice"
    assert merged["speakers"]["secondary"] == "Carol"

