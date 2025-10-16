"""Tests for the discovery engine keyword extraction helpers."""

from theo.domain.discoveries.engine import _top_keywords
from theo.domain.discoveries.models import DocumentEmbedding


def test_top_keywords_handles_string_metadata_keywords():
    """A string keyword metadata value should be treated as a single keyword."""

    embedding = DocumentEmbedding(
        document_id="doc-1",
        title="AI Research",
        abstract=None,
        topics=[],
        verse_ids=[],
        embedding=[0.1, 0.2, 0.3],
        metadata={"keywords": "Artificial Intelligence"},
    )

    keywords = _top_keywords([embedding], limit=3)

    assert keywords == ["artificial intelligence"]
