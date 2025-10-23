from types import SimpleNamespace

from theo.services.api.app.retriever.utils import compose_passage_meta


def test_compose_passage_meta_merges_document_and_passage_metadata() -> None:
    document = SimpleNamespace(
        title="Document Title",
        source_type="pdf",
        collection="library",
        authors=["Author"],
        doi="10.1000/example",
        venue="Conference",
        year=2024,
        source_url="https://example.com",
        topics=["Topic"],
        theological_tradition="catholic",
        topic_domains=["domain"],
        enrichment_version=3,
        provenance_score=0.75,
        bib_json={"primary_topic": "Grace"},
    )
    passage = SimpleNamespace(meta={"document_title": "Override", "extra": "value"})

    meta = compose_passage_meta(passage, document)

    assert meta["document_title"] == "Override"
    assert meta["source_type"] == "pdf"
    assert meta["collection"] == "library"
    assert meta["authors"] == ["Author"]
    assert meta["doi"] == "10.1000/example"
    assert meta["venue"] == "Conference"
    assert meta["year"] == 2024
    assert meta["source_url"] == "https://example.com"
    assert meta["topics"] == ["Topic"]
    assert meta["theological_tradition"] == "catholic"
    assert meta["topic_domains"] == ["domain"]
    assert meta["enrichment_version"] == 3
    assert meta["provenance_score"] == 0.75
    assert meta["primary_topic"] == "Grace"
    assert meta["extra"] == "value"


def test_compose_passage_meta_returns_none_when_empty() -> None:
    document = SimpleNamespace(
        title=None,
        source_type=None,
        collection=None,
        authors=None,
        doi=None,
        venue=None,
        year=None,
        source_url=None,
        topics=None,
        theological_tradition=None,
        topic_domains=None,
        enrichment_version=None,
        provenance_score=None,
        bib_json=None,
    )
    passage = SimpleNamespace(meta=None)

    assert compose_passage_meta(passage, document) is None
