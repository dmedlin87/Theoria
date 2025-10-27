from __future__ import annotations

from datetime import UTC, datetime
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

    def execute(self, stmt):  # pragma: no cover - exercised in tests
        if not self._executions:
            raise AssertionError("No scripted rows for statement execution")
        rows = self._executions.pop(0)
        return _FakeResult(rows)


class _SpanRecorder:
    def __init__(self):
        self.attributes: dict[str, object] = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
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


def _make_document(**overrides):
    base = {
        "id": "doc-1",
        "title": "Test Document",
        "source_type": "sermon",
        "collection": "research",
        "authors": ["Allowed"],
        "doi": None,
        "venue": None,
        "year": 2024,
        "source_url": "https://example.com",
        "topics": ["Grace"],
        "theological_tradition": "Catholic",
        "topic_domains": ["Ethics"],
        "enrichment_version": 1,
        "provenance_score": 10,
        "bib_json": {"primary_topic": "Grace"},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_passage(**overrides):
    base = {
        "id": "p-1",
        "document_id": "doc-1",
        "text": "Grace is abundant",
        "raw_text": "Grace is abundant",
        "osis_ref": "Gen.1.1",
        "start_char": 0,
        "end_char": 20,
        "page_no": 1,
        "t_start": None,
        "t_end": None,
        "meta": {"tei_search_blob": "Grace hope"},
        "lexeme": "tsvector",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_annotation(*, document_id: str, passage_id: str, body: str):
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    return DocumentAnnotationResponse(
        id=f"annotation-{passage_id}",
        document_id=document_id,
        type="note",
        body=body,
        passage_ids=[passage_id],
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.fixture
def tracer_stub(monkeypatch):
    tracer = _TracerStub()
    monkeypatch.setattr(hybrid, "_TRACER", tracer)
    return tracer


def _patch_annotation_helpers(monkeypatch, annotations_by_document):
    monkeypatch.setattr(
        hybrid,
        "load_annotations_for_documents",
        lambda session, doc_ids: {
            doc_id: annotations_by_document.get(doc_id, []) for doc_id in doc_ids
        },
    )

    def _index(mapping):
        by_passage: dict[str, list[DocumentAnnotationResponse]] = {}
        for annotations in mapping.values():
            for annotation in annotations:
                for passage_id in annotation.passage_ids or []:
                    by_passage.setdefault(passage_id, []).append(annotation)
        return by_passage

    monkeypatch.setattr(hybrid, "index_annotations_by_passage", _index)


def _patch_osis_helpers(monkeypatch, mapping: dict[str, set[int]]):
    def _expand(value):
        return mapping.get(value, set()) if value is not None else set()

    def _intersects(candidate, target):
        return bool(_expand(candidate) & _expand(target))

    monkeypatch.setattr(hybrid, "expand_osis_reference", _expand)
    monkeypatch.setattr(hybrid, "osis_intersects", _intersects)


def test_annotate_retrieval_span_records_request_fields():
    span = _SpanRecorder()
    request = HybridSearchRequest(
        query="Grace",
        osis="Gen.1.1",
        filters=HybridSearchFilters(
            collection="research",
            author="Allowed",
            source_type="sermon",
            theological_tradition="Catholic",
            topic_domain="Ethics",
        ),
        k=5,
        cursor="cursor-42",
        limit=25,
        mode="mentions",
    )

    hybrid._annotate_retrieval_span(span, request, cache_status="hit", backend="cached")

    assert span.attributes == {
        "retrieval.backend": "cached",
        "retrieval.cache_status": "hit",
        "retrieval.k": 5,
        "retrieval.limit": 25,
        "retrieval.cursor": "cursor-42",
        "retrieval.mode": "mentions",
        "retrieval.query": "Grace",
        "retrieval.osis": "Gen.1.1",
        "retrieval.filter.collection": "research",
        "retrieval.filter.author": "Allowed",
        "retrieval.filter.source_type": "sermon",
        "retrieval.filter.theological_tradition": "Catholic",
        "retrieval.filter.topic_domain": "Ethics",
    }


def test_fallback_search_filters_and_scores(monkeypatch, tracer_stub):
    annotations = {
        "doc-pass-a": [_make_annotation(document_id="doc-pass-a", passage_id="p-pass-a", body="Helpful insight")],
    }
    _patch_annotation_helpers(monkeypatch, annotations)
    _patch_osis_helpers(monkeypatch, {"Gen.1.1": {1}})

    doc_pass_a = _make_document(id="doc-pass-a")
    doc_pass_b = _make_document(id="doc-pass-b")
    doc_fail_author = _make_document(id="doc-fail-author", authors=["Other"])
    doc_fail_guard = _make_document(id="doc-fail-guard", topic_domains=["Doctrine"])
    doc_pass_tei = _make_document(id="doc-pass-tei")

    passage_pass_a = _make_passage(id="p-pass-a", document_id=doc_pass_a.id, text="Grace abounds", meta={})
    passage_pass_b = _make_passage(id="p-pass-b", document_id=doc_pass_b.id, text="Grace and grace together", meta={"tei": {"keywords": ["Grace"]}})
    passage_fail_author = _make_passage(id="p-fail-author", document_id=doc_fail_author.id)
    passage_fail_guard = _make_passage(id="p-fail-guard", document_id=doc_fail_guard.id)
    passage_pass_tei = _make_passage(
        id="p-pass-tei",
        document_id=doc_pass_tei.id,
        text="Love only",
        meta={"tei": {"keywords": ["Grace"]}},
        lexeme=None,
    )

    session = _FakeSession([
        [
            (passage_pass_a, doc_pass_a),
            (passage_pass_b, doc_pass_b),
            (passage_fail_author, doc_fail_author),
            (passage_fail_guard, doc_fail_guard),
            (passage_pass_tei, doc_pass_tei),
        ]
    ], dialect_name="sqlite")

    request = HybridSearchRequest(
        query="Grace",
        filters=HybridSearchFilters(author="Allowed", topic_domain="Ethics"),
        k=2,
    )

    results = hybrid._fallback_search(session, request)

    assert [result.document_id for result in results] == [doc_pass_b.id, doc_pass_a.id]
    assert all(result.rank == idx + 1 for idx, result in enumerate(results))
    assert all(result.document_rank == idx + 1 for idx, result in enumerate(results))
    assert results[0].score > results[1].score
    assert results[1].meta and results[1].meta["annotations"][0]["body"] == "Helpful insight"

    # Candidate passing through TEI scoring should be trimmed because only top-k are returned.
    assert all(result.document_id != doc_pass_tei.id for result in results)

    # Guardrails: excluded author and topic-domain mismatches never appear.
    excluded_ids = {doc_fail_author.id, doc_fail_guard.id}
    assert excluded_ids.isdisjoint({result.document_id for result in results})

    span_name, span = tracer_stub.spans[-1]
    assert span_name == "retriever.fallback"
    assert span.attributes["retrieval.hit_count"] == len(results)
    assert isinstance(span.attributes["retrieval.latency_ms"], float)


def test_fallback_search_osis_only_enforces_matches(monkeypatch, tracer_stub):
    _patch_annotation_helpers(monkeypatch, {})
    _patch_osis_helpers(monkeypatch, {"Gen.1.1": {1}, "Gen.1.2": {2}})

    doc_match = _make_document(id="doc-match")
    doc_miss = _make_document(id="doc-miss")

    passage_match = _make_passage(id="p-match", document_id=doc_match.id, osis_ref="Gen.1.1", text="Focused passage", meta={})
    passage_miss = _make_passage(id="p-miss", document_id=doc_miss.id, osis_ref="Gen.1.2", text="Another", meta={})

    session = _FakeSession([
        [
            (passage_match, doc_match),
            (passage_miss, doc_miss),
        ]
    ], dialect_name="sqlite")

    request = HybridSearchRequest(query=None, osis="Gen.1.1", k=2)

    results = hybrid._fallback_search(session, request)

    assert len(results) == 1
    assert results[0].document_id == doc_match.id
    assert pytest.approx(results[0].score, rel=1e-6) == pytest.approx(5.0, rel=1e-6)
    assert results[0].osis_distance == 0.0

    span_name, span = tracer_stub.spans[-1]
    assert span_name == "retriever.fallback"
    assert span.attributes["retrieval.hit_count"] == len(results)


def test_postgres_hybrid_search_combines_all_sources(monkeypatch, tracer_stub):
    annotations = {
        "doc-a": [_make_annotation(document_id="doc-a", passage_id="p-a", body="Grace note")],
    }
    _patch_annotation_helpers(monkeypatch, annotations)
    _patch_osis_helpers(
        monkeypatch,
        {"Gen.1.1": {1}, "Gen.1.2": {1, 2}, "Gen.1.3": {1, 3}},
    )

    monkeypatch.setattr(
        BinaryExpression,
        "astext",
        property(lambda self: self),
        raising=False,
    )

    monkeypatch.setattr(hybrid, "get_settings", lambda: SimpleNamespace(embedding_dim=3))
    monkeypatch.setattr(hybrid, "get_embedding_service", lambda: SimpleNamespace(embed=lambda values: [[0.1, 0.2, 0.3]]))

    doc_a = _make_document(id="doc-a")
    doc_b = _make_document(id="doc-b")
    doc_c = _make_document(id="doc-c")

    passage_a = _make_passage(id="p-a", document_id=doc_a.id, osis_ref="Gen.1.1", text="Grace and love", meta={"tei": {"keywords": ["Grace"]}})
    passage_b = _make_passage(id="p-b", document_id=doc_b.id, osis_ref="Gen.1.2", text="Graceful living", meta={})
    passage_c = _make_passage(id="p-c", document_id=doc_c.id, osis_ref="Gen.1.3", text="Mercy flows", meta={"tei": {"keywords": ["Grace"]}})

    vector_rows = [
        (passage_a, doc_a, 0.05, 0.9),
        (passage_b, doc_b, 0.1, 0.8),
    ]
    lexical_rows = [
        (passage_a, doc_a, 0.4),
        (passage_b, doc_b, 0.6),
        (passage_c, doc_c, 0.5),
    ]
    tei_rows = [
        (passage_c, doc_c),
    ]

    session = _FakeSession([vector_rows, lexical_rows, tei_rows], dialect_name="postgresql")

    request = HybridSearchRequest(query="Grace", osis="Gen.1.1", k=3)

    results = hybrid._postgres_hybrid_search(session, request)

    assert {result.document_id for result in results} == {doc_a.id, doc_b.id, doc_c.id}
    assert [result.rank for result in results] == [1, 2, 3]
    assert [result.document_rank for result in results] == [1, 2, 3]

    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True)

    result_by_doc = {result.document_id: result for result in results}
    assert pytest.approx(result_by_doc[doc_a.id].vector_score, rel=1e-6) == pytest.approx(0.9, rel=1e-6)
    assert pytest.approx(result_by_doc[doc_a.id].lexical_score, rel=1e-6) == pytest.approx(0.4, rel=1e-6)
    assert result_by_doc[doc_a.id].osis_distance == 0.0
    assert result_by_doc[doc_a.id].meta["annotations"][0]["body"] == "Grace note"

    assert pytest.approx(result_by_doc[doc_b.id].vector_score, rel=1e-6) == pytest.approx(0.8, rel=1e-6)
    assert pytest.approx(result_by_doc[doc_b.id].lexical_score, rel=1e-6) == pytest.approx(0.6, rel=1e-6)

    assert result_by_doc[doc_c.id].vector_score is None
    assert pytest.approx(result_by_doc[doc_c.id].lexical_score, rel=1e-6) == pytest.approx(0.5, rel=1e-6)

    span_name, span = tracer_stub.spans[-1]
    assert span_name == "retriever.postgres"
    assert span.attributes["retrieval.hit_count"] == len(results)


def test_postgres_hybrid_search_osis_only_branch(monkeypatch, tracer_stub):
    _patch_annotation_helpers(monkeypatch, {})
    _patch_osis_helpers(monkeypatch, {"Gen.1.1": {1}, "Gen.1.2": {2}})

    monkeypatch.setattr(hybrid, "get_settings", lambda: SimpleNamespace(embedding_dim=3))
    monkeypatch.setattr(hybrid, "get_embedding_service", lambda: SimpleNamespace(embed=lambda values: [[0.0, 0.0, 0.0]]))

    doc = _make_document(id="doc-osis")
    passage = _make_passage(id="p-osis", document_id=doc.id, osis_ref="Gen.1.1", meta={})

    session = _FakeSession([[ (passage, doc) ]], dialect_name="postgresql")

    request = HybridSearchRequest(query=None, osis="Gen.1.1", k=1)

    results = hybrid._postgres_hybrid_search(session, request)

    assert len(results) == 1
    assert results[0].document_id == doc.id
    assert results[0].osis_distance == 0.0
    assert pytest.approx(results[0].score, rel=1e-6) == pytest.approx(0.3, rel=1e-6)

    span_name, span = tracer_stub.spans[-1]
    assert span_name == "retriever.postgres"
    assert span.attributes["retrieval.hit_count"] == len(results)


def test_hybrid_search_uses_fallback_backend(monkeypatch, tracer_stub):
    times = iter([100.0, 100.5])
    monkeypatch.setattr(hybrid, "perf_counter", lambda: next(times))

    stub_results = [SimpleNamespace(id="fallback", document_id="doc", score=1.0)]
    captured: dict[str, object] = {}

    def _fake_fallback(session, request):
        captured["session"] = session
        captured["request"] = request
        return stub_results

    def _unexpected_postgres(*_args, **_kwargs):
        raise AssertionError("Postgres backend should not be used for fallback tests")

    monkeypatch.setattr(hybrid, "_fallback_search", _fake_fallback)
    monkeypatch.setattr(hybrid, "_postgres_hybrid_search", _unexpected_postgres)

    session = _FakeSession([], dialect_name=None)
    request = HybridSearchRequest(query="Grace", k=1)

    results = hybrid.hybrid_search(session, request)

    assert results is stub_results
    assert captured["session"] is session
    assert captured["request"] is request

    span_name, span = tracer_stub.spans[-1]
    assert span_name == "retriever.hybrid"
    assert span.attributes["retrieval.backend"] == "hybrid"
    assert span.attributes["retrieval.cache_status"] == "miss"
    assert span.attributes["retrieval.selected_backend"] == "fallback"
    assert span.attributes["retrieval.hit_count"] == len(stub_results)
    assert span.attributes["retrieval.latency_ms"] == 500.0


def test_hybrid_search_uses_postgres_backend(monkeypatch, tracer_stub):
    times = iter([200.0, 200.123])
    monkeypatch.setattr(hybrid, "perf_counter", lambda: next(times))

    stub_results = [SimpleNamespace(id="postgres", document_id="doc", score=2.0)]
    captured: dict[str, object] = {}

    def _fake_postgres(session, request):
        captured["session"] = session
        captured["request"] = request
        return stub_results

    def _unexpected_fallback(*_args, **_kwargs):
        raise AssertionError("Fallback backend should not be used for postgres tests")

    monkeypatch.setattr(hybrid, "_postgres_hybrid_search", _fake_postgres)
    monkeypatch.setattr(hybrid, "_fallback_search", _unexpected_fallback)

    session = _FakeSession([], dialect_name="postgresql")
    request = HybridSearchRequest(query="Grace", k=2)

    results = hybrid.hybrid_search(session, request)

    assert results is stub_results
    assert captured["session"] is session
    assert captured["request"] is request

    span_name, span = tracer_stub.spans[-1]
    assert span_name == "retriever.hybrid"
    assert span.attributes["retrieval.backend"] == "hybrid"
    assert span.attributes["retrieval.cache_status"] == "miss"
    assert span.attributes["retrieval.selected_backend"] == "postgresql"
    assert span.attributes["retrieval.hit_count"] == len(stub_results)
    assert span.attributes["retrieval.latency_ms"] == 123.0


def test_postgres_hybrid_search_falls_back_for_non_postgres(monkeypatch):
    monkeypatch.setattr(hybrid, "get_settings", lambda: SimpleNamespace(embedding_dim=3))
    monkeypatch.setattr(hybrid, "get_embedding_service", lambda: SimpleNamespace(embed=lambda values: values))

    captured = {}

    def _fake_fallback(session, request):
        captured["called"] = True
        return [SimpleNamespace(id="fallback", document_id="doc", score=1.0, rank=1)]

    monkeypatch.setattr(hybrid, "_fallback_search", _fake_fallback)

    session = _FakeSession([], dialect_name="sqlite")
    request = HybridSearchRequest(query="Grace", k=1)

    results = hybrid._postgres_hybrid_search(session, request)

    assert captured.get("called") is True
    assert results[0].id == "fallback"
