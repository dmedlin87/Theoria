"""Compatibility helpers for research note persistence."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Mapping
from warnings import warn

from sqlalchemy.orm import Session

from theo.application.facades.research import (
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    get_research_service,
)
from theo.domain.research import ResearchNote
from theo.domain.research.entities import ResearchNoteNotFoundError

warn(
    "Importing from 'theo.services.api.app.research.notes' is deprecated; "
    "use 'theo.application.facades.research' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "ResearchNote",
    "ResearchNoteNotFoundError",
    "create_research_note",
    "generate_research_note_preview",
    "get_notes_for_osis",
    "update_research_note",
    "delete_research_note",
]


def _draft_from_kwargs(**kwargs: Any) -> ResearchNoteDraft:
    evidences_payload = kwargs.pop("evidences", ())
    tags_payload = kwargs.pop("tags", None)
    tags_tuple: tuple[str, ...] | None = None
    if tags_payload is not None:
        tags_tuple = tuple(tag for tag in tags_payload if tag)
    evidence_models: tuple[ResearchNoteEvidenceDraft, ...] = ()
    if evidences_payload:
        evidence_models = tuple(
            ResearchNoteEvidenceDraft(
                source_type=evidence.get("source_type"),
                source_ref=evidence.get("source_ref"),
                osis_refs=tuple(evidence.get("osis_refs") or []) or None,
                citation=evidence.get("citation"),
                snippet=evidence.get("snippet"),
                meta=evidence.get("meta"),
            )
            for evidence in evidences_payload
        )
    return ResearchNoteDraft(
        evidences=evidence_models,
        tags=tags_tuple,
        **kwargs,
    )


def create_research_note(
    session: Session,
    *,
    commit: bool = True,
    **kwargs: Any,
) -> ResearchNote:
    service = get_research_service(session)
    draft = _draft_from_kwargs(**kwargs)
    return service.create_note(draft, commit=commit)


def generate_research_note_preview(session: Session, **kwargs: Any) -> ResearchNote:
    service = get_research_service(session)
    draft = _draft_from_kwargs(**kwargs)
    return service.preview_note(draft)


def get_notes_for_osis(
    session: Session,
    osis: str,
    *,
    stance: str | None = None,
    claim_type: str | None = None,
    tag: str | None = None,
    min_confidence: float | None = None,
) -> list[ResearchNote]:
    service = get_research_service(session)
    return service.list_notes(
        osis,
        stance=stance,
        claim_type=claim_type,
        tag=tag,
        min_confidence=min_confidence,
    )


def update_research_note(
    session: Session,
    note_id: str,
    *,
    changes: Mapping[str, Any],
    evidences: Iterable[dict] | None = None,
) -> ResearchNote:
    service = get_research_service(session)
    evidence_models: tuple[ResearchNoteEvidenceDraft, ...] | None = None
    if evidences is not None:
        evidence_models = tuple(
            ResearchNoteEvidenceDraft(
                source_type=evidence.get("source_type"),
                source_ref=evidence.get("source_ref"),
                osis_refs=tuple(evidence.get("osis_refs") or []) or None,
                citation=evidence.get("citation"),
                snippet=evidence.get("snippet"),
                meta=evidence.get("meta"),
            )
            for evidence in evidences
        )
    return service.update_note(
        note_id,
        changes,
        evidences=evidence_models,
    )


def delete_research_note(session: Session, note_id: str) -> None:
    service = get_research_service(session)
    service.delete_note(note_id)
