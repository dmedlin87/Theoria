from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given, strategies as st

from theo.infrastructure.api.app.ingest.metadata import (
    HTMLMetadataParser,
    HTMLTextExtractor,
    _normalise_guardrail_collection,
    _normalise_guardrail_value,
    build_source_ref,
    collect_topics,
    coerce_date,
    coerce_datetime,
    coerce_int,
    ensure_list,
    extract_guardrail_profile,
    merge_metadata,
    normalise_source_url,
    normalise_topics_field,
    parse_frontmatter_from_markdown,
    serialise_frontmatter,
    truncate,
)


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


def test_serialise_frontmatter_renders_supported_types(tmp_path: Path) -> None:
    now = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    payload = {
        "string": "value",
        "number": 7,
        "path": tmp_path,
        "list": [1, 2, 3],
        "date": date(2024, 1, 1),
        "datetime": now,
    }

    windows_path = "C:" + "\\" + "Users" + "\\" + "example"
    payload["windows_path"] = windows_path

    rendered = serialise_frontmatter(payload)

    assert "2024-01-01" in rendered
    assert "2024-01-02T03:04:05+00:00" in rendered
    assert str(tmp_path) in rendered
    assert windows_path in rendered


@given(st.lists(st.one_of(st.text(min_size=0, max_size=5), st.none(), st.integers()), max_size=8))
def test_normalise_guardrail_collection_deduplicates(values: list[object | None]) -> None:
    result = _normalise_guardrail_collection(values)

    if result is None:
        assert all(not _normalise_guardrail_value(value) for value in values)
        return

    lowered = [item.lower() for item in result]
    assert lowered == sorted(set(lowered), key=lowered.index)
    assert all(item == item.strip() and item for item in result)


def test_normalise_guardrail_collection_from_delimited_string() -> None:
    result = _normalise_guardrail_collection(" grace ;   justice,Grace ;mercy ")
    assert result == ["grace", "justice", "mercy"]


def test_extract_guardrail_profile_combines_tradition_and_tags() -> None:
    frontmatter = {
        "theological_tradition": " Anglican  ",
        "topic_domains": ["Justice"],
        "admin_tags": ["domain:Mercy", "misc"],
        "tags": ["Topic_Domain:Mercy", "topic_domain:charity"],
    }

    tradition, topic_domains = extract_guardrail_profile(frontmatter)

    assert tradition == "Anglican"
    assert topic_domains == ["Justice", "Mercy", "charity"]


def test_collect_topics_merges_document_and_frontmatter() -> None:
    document = SimpleNamespace(topics={"all": ["justice", "mercy"]})
    frontmatter = {"topics": ["mercy", "charity"]}

    topics = collect_topics(document, frontmatter)

    assert topics == ["justice", "mercy", "charity"]


def test_normalise_topics_field_preserves_order() -> None:
    data = normalise_topics_field(["Justice"], [" justice "], " Mercy ")
    assert data == {"primary": "Justice", "all": ["Justice", "justice", "Mercy"]}


def test_build_source_ref_formats_timestamp() -> None:
    ref = build_source_ref("abc", "https://youtube.com/watch?v=abc", 125.0)
    assert ref == "youtube:abc#t=02:05"


def test_build_source_ref_requires_identifier_and_time() -> None:
    assert build_source_ref(None, "https://youtube.com/watch?v=abc", 10.0) is None
    assert build_source_ref("abc", "https://youtube.com/watch?v=abc", None) is None


def test_coerce_helpers_normalise_inputs() -> None:
    assert coerce_date("2024-01-02") == date(2024, 1, 2)
    assert coerce_date(datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)) == date(2024, 1, 2)
    assert coerce_date("not-a-date") is None

    midnight = datetime(2024, 1, 2, 0, 0)
    assert coerce_datetime(midnight).tzinfo == timezone.utc
    assert coerce_datetime("2024-01-02T00:00:00+01:00").tzinfo is not None
    assert coerce_datetime("invalid") is None

    assert coerce_int("7") == 7
    assert coerce_int(7.8) == 7
    assert coerce_int("bad") is None


def test_ensure_list_handles_scalars_and_none() -> None:
    assert ensure_list(None) is None
    assert ensure_list(["a", 2]) == ["a", "2"]
    assert ensure_list("solo") == ["solo"]


def test_parse_frontmatter_from_markdown_handles_missing_delimiter() -> None:
    frontmatter, body = parse_frontmatter_from_markdown("---\ntitle: Example\nbody")
    assert frontmatter == {}
    assert body == "---\ntitle: Example\nbody"

    frontmatter, body = parse_frontmatter_from_markdown("---\ntitle: Example\n---\nBody")
    assert frontmatter == {"title": "Example"}
    assert body == "Body"


def test_normalise_source_url_allows_relative_and_absolute() -> None:
    assert normalise_source_url(" https://Example.com/path ") == "https://Example.com/path"
    assert normalise_source_url("//example.com/path") == "/example.com/path"
    assert normalise_source_url("/docs/page") == "/docs/page"
    assert normalise_source_url("javascript:alert(1)") is None


def test_html_metadata_parser_extracts_title_and_canonical() -> None:
    parser = HTMLMetadataParser()
    parser.feed(
        """<html><head><title>Example</title><link rel='canonical' href='https://example.com'></head></html>"""
    )
    parser.close()
    assert parser.title == "Example"
    assert parser.canonical_url == "https://example.com"


def test_html_text_extractor_skips_scripts() -> None:
    extractor = HTMLTextExtractor()
    extractor.feed("<html><body><script>ignore</script><p>Hello</p><div>World</div></body></html>")
    extractor.close()
    assert extractor.get_text() == "Hello\nWorld"


@pytest.mark.parametrize(
    "text,limit,expected",
    [
        ("short", 10, "short"),
        ("  needs trim  ", 8, "needs..."),
        ("x" * 50, 10, "xxxxxxx..."),
    ],
)
def test_truncate_limits_length(text: str, limit: int, expected: str) -> None:
    assert truncate(text, limit) == expected
