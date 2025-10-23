"""Helpers for working with structured document annotations."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Iterable, Mapping

from sqlalchemy.orm import Session

from theo.services.api.app.persistence_models import DocumentAnnotation

from ..models.documents import (
    AnnotationType,
    DocumentAnnotationCreate,
    DocumentAnnotationResponse,
)

_ALLOWED_TYPES: set[str] = {"claim", "evidence", "question", "note"}


def _normalise_type(value: str | None) -> AnnotationType:
    if not value:
        return "note"
    lowered = value.strip().lower()
    if lowered not in _ALLOWED_TYPES:
        return "note"
    return lowered  # type: ignore[return-value]


def prepare_annotation_body(payload: DocumentAnnotationCreate) -> str:
    """Serialise an annotation payload into a JSON document for storage."""

    annotation_type = _normalise_type(payload.type)
    text = (payload.text or "").strip()
    if not text:
        raise ValueError("Annotation text cannot be empty")

    stance = (payload.stance or "").strip() or None
    group_id = (payload.group_id or "").strip() or None
    passage_ids = list(dict.fromkeys(payload.passage_ids))
    metadata = payload.metadata or None

    document = {
        "type": annotation_type,
        "text": text,
    }
    if stance:
        document["stance"] = stance
    if passage_ids:
        document["passage_ids"] = passage_ids
    if group_id:
        document["group_id"] = group_id
    if metadata:
        document["metadata"] = metadata

    return json.dumps(document, ensure_ascii=False)


def annotation_to_schema(annotation: DocumentAnnotation) -> DocumentAnnotationResponse:
    """Convert a database annotation row into an API schema."""

    raw = annotation.body or ""
    parsed: dict | None = None
    body = raw
    stance: str | None = None
    group_id: str | None = None
    passage_ids: list[str] = []
    metadata: dict | None = None
    legacy = True
    annotation_type: AnnotationType = "note"

    try:
        candidate = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        candidate = None

    if isinstance(candidate, dict):
        parsed = candidate
        annotation_type = _normalise_type(candidate.get("type"))
        text_value = candidate.get("text")
        if isinstance(text_value, str) and text_value.strip():
            body = text_value.strip()
        stance_value = candidate.get("stance")
        if isinstance(stance_value, str) and stance_value.strip():
            stance = stance_value.strip()
        group_value = candidate.get("group_id")
        if isinstance(group_value, str) and group_value.strip():
            group_id = group_value.strip()
        passage_value = candidate.get("passage_ids")
        if isinstance(passage_value, (list, tuple, set)):
            cleaned: list[str] = []
            for item in passage_value:
                candidate_id = str(item).strip()
                if candidate_id:
                    cleaned.append(candidate_id)
            passage_ids = list(dict.fromkeys(cleaned))
        metadata_value = candidate.get("metadata")
        if isinstance(metadata_value, dict):
            metadata = metadata_value
        legacy = False

    return DocumentAnnotationResponse(
        id=annotation.id,
        document_id=annotation.document_id,
        type=annotation_type,
        body=body,
        stance=stance,
        passage_ids=passage_ids,
        group_id=group_id,
        metadata=metadata,
        raw=parsed,
        legacy=legacy,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


def load_annotations_for_documents(
    session: Session, document_ids: Iterable[str]
) -> dict[str, list[DocumentAnnotationResponse]]:
    """Fetch annotations for the supplied documents keyed by document ID."""

    ids = {doc_id for doc_id in document_ids if doc_id}
    if not ids:
        return {}

    rows = (
        session.query(DocumentAnnotation)
        .filter(DocumentAnnotation.document_id.in_(ids))
        .order_by(DocumentAnnotation.created_at.asc())
        .all()
    )

    grouped: dict[str, list[DocumentAnnotationResponse]] = defaultdict(list)
    for row in rows:
        grouped[row.document_id].append(annotation_to_schema(row))
    return grouped


def index_annotations_by_passage(
    annotations_by_document: Mapping[str, list[DocumentAnnotationResponse]]
) -> dict[str, list[DocumentAnnotationResponse]]:
    """Build a passage-centric index for annotation lookups."""

    index: dict[str, list[DocumentAnnotationResponse]] = defaultdict(list)
    for annotation_list in annotations_by_document.values():
        for annotation in annotation_list:
            for passage_id in annotation.passage_ids:
                index[passage_id].append(annotation)
    return index
