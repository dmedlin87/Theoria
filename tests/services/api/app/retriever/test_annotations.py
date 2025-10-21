"""Tests for annotation helpers in retriever package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import pytest

from theo.services.api.app.retriever.annotations import (
    annotation_to_schema,
    index_annotations_by_passage,
    load_annotations_for_documents,
    prepare_annotation_body,
)
from theo.services.api.app.models.documents import (
    DocumentAnnotationCreate,
    DocumentAnnotationResponse,
)
from theo.services.api.app.persistence_models import DocumentAnnotation


@dataclass
class _FakeAnnotationRow:
    """Lightweight stand-in for ``DocumentAnnotation`` rows."""

    id: str
    document_id: str
    body: str
    created_at: datetime
    updated_at: datetime


class _FakeQuery:
    def __init__(self, rows: list[_FakeAnnotationRow]):
        self._rows = rows

    def filter(self, condition):  # pragma: no cover - passthrough
        return self

    def order_by(self, *args):  # pragma: no cover - passthrough
        return self

    def all(self) -> list[_FakeAnnotationRow]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[_FakeAnnotationRow]):
        self._rows = rows
        self.requested_models: list[type] = []

    def query(self, model):  # pragma: no cover - passthrough
        self.requested_models.append(model)
        return _FakeQuery(self._rows)


def _make_payload(**overrides) -> DocumentAnnotationCreate:
    base = {
        "type": "note",
        "text": "  Example text  ",
        "stance": "  supportive  ",
        "group_id": "  group-1  ",
        "passage_ids": ["p1", "p2", "p1"],
        "metadata": {"confidence": 0.9},
    }
    base.update(overrides)
    return DocumentAnnotationCreate(**base)


def _make_row(*, document_id: str, body: str, row_id: str = "ann-1") -> _FakeAnnotationRow:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return _FakeAnnotationRow(
        id=row_id,
        document_id=document_id,
        body=body,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_prepare_annotation_body_normalises_payload() -> None:
    payload = _make_payload(passage_ids=["p1", "p2", "p1", " "], metadata={"extra": "yes"})

    document = prepare_annotation_body(payload)

    assert document == (
        '{"type": "note", "text": "Example text", "stance": "supportive", '
        '"passage_ids": ["p1", "p2"], "group_id": "group-1", "metadata": {"extra": "yes"}}'
    )


def test_prepare_annotation_body_omits_empty_optional_fields() -> None:
    payload = _make_payload(
        stance=None,
        group_id=" ",
        passage_ids=[],
        metadata=None,
    )

    document = prepare_annotation_body(payload)

    assert document == '{"type": "note", "text": "Example text"}'


def test_annotation_to_schema_handles_structured_body() -> None:
    body = '{"type": "evidence", "text": "Supporting statement", "passage_ids": [1, "p2", "p2"], "metadata": {"foo": "bar"}}'
    row = _make_row(document_id="doc-1", body=body)

    response = annotation_to_schema(row)  # type: ignore[arg-type]

    assert response.type == "evidence"
    assert response.body == "Supporting statement"
    assert response.passage_ids == ["1", "p2"]
    assert response.metadata == {"foo": "bar"}
    assert response.legacy is False
    assert response.raw == {
        "type": "evidence",
        "text": "Supporting statement",
        "passage_ids": [1, "p2", "p2"],
        "metadata": {"foo": "bar"},
    }


def test_annotation_to_schema_handles_legacy_string_body() -> None:
    row = _make_row(document_id="doc-legacy", body="Legacy note")

    response = annotation_to_schema(row)  # type: ignore[arg-type]

    assert response.body == "Legacy note"
    assert response.type == "note"
    assert response.legacy is True
    assert response.raw is None


def test_load_annotations_for_documents_groups_by_document() -> None:
    rows = [
        _make_row(document_id="doc-1", body="{\"text\": \"First\"}", row_id="a1"),
        _make_row(document_id="doc-1", body="{\"text\": \"Second\"}", row_id="a2"),
        _make_row(document_id="doc-2", body="{\"text\": \"Third\"}", row_id="a3"),
    ]
    session = _FakeSession(rows)

    grouped = load_annotations_for_documents(session, ["doc-1", "doc-2", "", "doc-1"])

    assert session.requested_models == [DocumentAnnotation]
    assert list(grouped.keys()) == ["doc-1", "doc-2"]
    assert [annotation.body for annotation in grouped["doc-1"]] == ["First", "Second"]
    assert [annotation.body for annotation in grouped["doc-2"]] == ["Third"]


def test_load_annotations_for_documents_returns_empty_for_no_ids() -> None:
    session = _FakeSession([])

    grouped = load_annotations_for_documents(session, ["", None, "   "])  # type: ignore[list-item]

    assert grouped == {}


def test_index_annotations_by_passage_maps_ids() -> None:
    annotations = {
        "doc-1": [
            DocumentAnnotationResponse(
                id="a1",
                document_id="doc-1",
                type="note",
                body="First",
                passage_ids=["p1", "p2"],
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )
        ],
        "doc-2": [
            DocumentAnnotationResponse(
                id="a2",
                document_id="doc-2",
                type="claim",
                body="Second",
                passage_ids=["p2", "p3"],
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )
        ],
    }

    index = index_annotations_by_passage(annotations)

    assert set(index.keys()) == {"p1", "p2", "p3"}
    assert [annotation.id for annotation in index["p2"]] == ["a1", "a2"]
    assert [annotation.id for annotation in index["p1"]] == ["a1"]
