from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.sql.elements import BinaryExpression

from theo.infrastructure.api.app.models.documents import DocumentAnnotationResponse
from theo.infrastructure.api.app.models.search import HybridSearchFilters, HybridSearchRequest
from theo.infrastructure.api.app.retriever import hybrid


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class _FakeSession:
    def __init__(self, executions, *, dialect_name: str | None = "postgresql"):
        self._executions = list(executions)
        if dialect_name is None:
            self.bind = None
        else:
            self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))

    def execute(self, _stmt):
        if not self._executions:
            raise AssertionError("No scripted rows for statement execution")
        rows = self._executions.pop(0)
        return _FakeResult(rows)


class _SpanRecorder:
    def __init__(self):
        self.attributes: dict[str, object] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def set_attribute(self, key, value):
        self.attributes[key] = value


class _TracerStub:
    def __init__(self):
        self.spans: list[tuple[str, _SpanRecorder]] = []

    def start_as_current_span(self, name):
        span = _SpanRecorder()
        self.spans.append((name, span))
        return span


@pytest.fixture(autouse=True)
def _patch_binary_expression(monkeypatch):
    monkeypatch.setattr(
        BinaryExpression,
        "astext",
        property(lambda self: self),
        raising=False,
    )


@pytest.fixture
def tracer_stub(monkeypatch):
    tracer = _TracerStub()
    monkeypatch.setattr(hybrid, "_TRACER", tracer)
    return tracer


@pytest.fixture
def seeded_document():
    return SimpleNamespace(
        id="doc-alpha",
        title="Alpha Document",
        source_type="sermon",
        collection="research",
        authors=["Alpha"],
        doi=None,
        venue=None,
        year=2024,
        source_url=None,
        topics=["Grace"],
        theological_tradition="Catholic",
        topic_domains=["Ethics"],
        enrichment_version=1,
        provenance_score=0.5,
        bib_json={"primary_topic": "Grace"},
    )


@pytest.fixture
def seeded_passage(seeded_document):
    return SimpleNamespace(
        id="passage-alpha",
        document_id=seeded_document.id,
        text="Grace appears often",
        raw_text="Grace appears often",
        osis_ref="Gen.1.1",
        start_char=0,
        end_char=21,
        page_no=1,
        t_start=None,
        t_end=None,
        meta={"tei": {"keywords": ["Grace"]}, "tei_search_blob": "Grace hope"},
        lexeme="tsvector",
    )


def _make_document(identifier: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier,
        title=f"Document {identifier}",
        source_type="sermon",
        collection="research",
        authors=[identifier.title()],
        doi=None,
        venue=None,
        year=2024,
        source_url=None,
        topics=["Grace"],
        theological_tradition="Catholic",
        topic_domains=["Ethics"],
        enrichment_version=1,
        provenance_score=0.5,
        bib_json={"primary_topic": "Grace"},
    )


def _make_passage(identifier: str, document_id: str, text: str, *, osis_ref: str | None = None):
    return SimpleNamespace(
        id=identifier,
        document_id=document_id,
        text=text,
        raw_text=text,
        osis_ref=osis_ref,
        start_char=0,
        end_char=len(text),
        page_no=1,
        t_start=None,
        t_end=None,
        meta={"tei": {"keywords": text.split()}, "tei_search_blob": text},
        lexeme="tsvector",
    )


def _patch_annotation_helpers(monkeypatch, annotations_by_document: dict[str, list[DocumentAnnotationResponse]]):
    monkeypatch.setattr(
        hybrid,
        "load_annotations_for_documents",
        lambda _session, doc_ids: {
            doc_id: annotations_by_document.get(doc_id, []) for doc_id in doc_ids
        },
    )

    def _index(mapping):
        by_passage: dict[str, list[DocumentAnnotationResponse]] = {}
        for annotations in mapping.values():
            for annotation in annotations:
                for passage_id in annotation.passage_ids:
                    by_passage.setdefault(passage_id, []).append(annotation)
        return by_passage

    monkeypatch.setattr(hybrid, "index_annotations_by_passage", _index)


@pytest.fixture
def annotation_map(seeded_document, seeded_passage):
    annotation = DocumentAnnotationResponse(
        id="ann-alpha",
        document_id=seeded_document.id,
        type="note",
        body="Grace commentary",
        passage_ids=[seeded_passage.id],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    return {seeded_document.id: [annotation]}


def _patch_osis_helpers(monkeypatch, mapping: dict[str, set[int]]):
    def _expand(value):
        return mapping.get(value, set()) if value is not None else set()

    def _intersects(candidate, target):
        return bool(_expand(candidate) & _expand(target))

    monkeypatch.setattr(hybrid, "expand_osis_reference", _expand)
    monkeypatch.setattr(hybrid, "osis_intersects", _intersects)


def test_hybrid_ann_hnsw_parity(monkeypatch, tracer_stub, annotation_map):
    _patch_annotation_helpers(monkeypatch, annotation_map)
    _patch_osis_helpers(monkeypatch, {"Gen.1.1": {1}})

    doc_alpha = _make_document("doc-alpha")
    doc_beta = _make_document("doc-beta")

    passage_alpha = _make_passage(
        "passage-alpha",
        doc_alpha.id,
        "Grace and mercy unite",
        osis_ref="Gen.1.1",
    )
    passage_beta = _make_passage(
        "passage-beta",
        doc_beta.id,
        "Grace inspires",
        osis_ref="Gen.1.1",
    )

    vector_rows = [
        (passage_alpha, doc_alpha, 0.05, 0.9),
        (passage_beta, doc_beta, 0.2, 0.5),
    ]
    lexical_rows = [
        (passage_alpha, doc_alpha, 0.6),
        (passage_beta, doc_beta, 0.7),
    ]
    tei_rows = []

    postgres_session = _FakeSession([vector_rows, lexical_rows, tei_rows], dialect_name="postgresql")

    monkeypatch.setattr(hybrid, "get_settings", lambda: SimpleNamespace(embedding_dim=3))
    monkeypatch.setattr(
        hybrid,
        "get_embedding_service",
        lambda: SimpleNamespace(embed=lambda values: [[0.1, 0.2, 0.3]]),
    )

    request = HybridSearchRequest(query="Grace", osis="Gen.1.1", k=2)

    postgres_results = hybrid._postgres_hybrid_search(postgres_session, request)

    fallback_rows = [
        (passage_alpha, doc_alpha),
        (passage_beta, doc_beta),
    ]
    fallback_session = _FakeSession([fallback_rows], dialect_name="sqlite")
    fallback_results = hybrid._fallback_search(fallback_session, request)

    assert [res.document_id for res in postgres_results] == [res.document_id for res in fallback_results]
    assert postgres_results[0].document_id == doc_alpha.id
    assert fallback_results[0].document_id == doc_alpha.id


def test_hybrid_reranking_prefers_combined_scores(monkeypatch, tracer_stub):
    _patch_annotation_helpers(monkeypatch, {})
    _patch_osis_helpers(monkeypatch, {"Gen.1.1": {1}})

    doc_primary = _make_document("doc-primary")
    doc_secondary = _make_document("doc-secondary")

    passage_primary = _make_passage("p-primary", doc_primary.id, "Grace harmony", osis_ref="Gen.1.1")
    passage_secondary = _make_passage("p-secondary", doc_secondary.id, "Grace wisdom", osis_ref="Gen.1.1")

    vector_rows = [
        (passage_primary, doc_primary, 0.02, 0.95),
        (passage_secondary, doc_secondary, 0.01, 0.6),
    ]
    lexical_rows = [
        (passage_primary, doc_primary, 0.3),
        (passage_secondary, doc_secondary, 0.8),
    ]
    tei_rows = []

    postgres_session = _FakeSession([vector_rows, lexical_rows, tei_rows], dialect_name="postgresql")

    monkeypatch.setattr(hybrid, "get_settings", lambda: SimpleNamespace(embedding_dim=3))
    monkeypatch.setattr(
        hybrid,
        "get_embedding_service",
        lambda: SimpleNamespace(embed=lambda values: [[0.1, 0.2, 0.3]]),
    )

    request = HybridSearchRequest(query="Grace", osis="Gen.1.1", k=2)
    results = hybrid._postgres_hybrid_search(postgres_session, request)

    assert [res.document_id for res in results] == [doc_primary.id, doc_secondary.id]
    assert results[0].score >= results[1].score
    assert results[0].rank == 1 and results[1].rank == 2


@pytest.mark.parametrize("query", ["", "#$%^&*"])
def test_hybrid_search_handles_edge_case_queries(monkeypatch, tracer_stub, query):
    _patch_annotation_helpers(monkeypatch, {})
    _patch_osis_helpers(monkeypatch, {})

    monkeypatch.setattr(hybrid, "get_settings", lambda: SimpleNamespace(embedding_dim=3))
    monkeypatch.setattr(
        hybrid,
        "get_embedding_service",
        lambda: SimpleNamespace(embed=lambda values: [[0.0, 0.0, 0.0]]),
    )

    session = _FakeSession([[], [], []], dialect_name="postgresql")

    request = HybridSearchRequest(query=query, filters=HybridSearchFilters(), k=3)

    results = hybrid.hybrid_search(session, request)

    assert results == []
    hybrid_span = next(
        span for name, span in tracer_stub.spans if name == "retriever.hybrid"
    )
    assert hybrid_span.attributes["retrieval.hit_count"] == 0
