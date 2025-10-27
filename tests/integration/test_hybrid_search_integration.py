from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from theo.infrastructure.api.app.models.search import HybridSearchFilters, HybridSearchRequest
from theo.infrastructure.api.app.persistence_models import Document as DocumentRecord
from theo.infrastructure.api.app.persistence_models import Passage
from theo.infrastructure.api.app.retriever import hybrid as hybrid_module

pytestmark = pytest.mark.schema


class _SpanContext:
    def __init__(self, span: "_StubSpan") -> None:
        self._span = span

    def __enter__(self) -> "_StubSpan":
        return self._span

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _StubSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class _StubTracer:
    def __init__(self) -> None:
        self.spans: list[_StubSpan] = []

    def start_as_current_span(self, name: str) -> _SpanContext:
        span = _StubSpan(name)
        self.spans.append(span)
        return _SpanContext(span)


def test_hybrid_search_fallback_records_latency(
    monkeypatch: pytest.MonkeyPatch, sqlite_session: Session
) -> None:
    """Execute fallback hybrid search and capture performance instrumentation."""

    tracer = _StubTracer()
    monkeypatch.setattr(hybrid_module, "_TRACER", tracer)

    now = datetime.now(timezone.utc)
    document = DocumentRecord(
        id="doc-search",
        title="Creation Theology",
        collection="research",
        created_at=now,
        updated_at=now,
        bib_json={"language": "en", "tags": ["creation"]},
    )
    sqlite_session.add(document)
    sqlite_session.add(
        Passage(
            id="passage-search",
            document_id=document.id,
            text="Let there be light, and there was light.",
            raw_text="Let there be light, and there was light.",
            tokens=12,
            osis_ref="Gen.1.3",
        )
    )
    sqlite_session.flush()

    request = HybridSearchRequest(
        query="light",
        filters=HybridSearchFilters(collection="research"),
        k=5,
    )
    results = hybrid_module.hybrid_search(sqlite_session, request)

    assert results
    assert results[0].document_title == "Creation Theology"

    recorded = {span.name: span for span in tracer.spans}
    assert "retriever.fallback" in recorded
    span = recorded["retriever.fallback"]
    assert "retrieval.latency_ms" in span.attributes
    assert span.attributes["retrieval.backend"] == "fallback"
