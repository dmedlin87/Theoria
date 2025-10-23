"""SQLAlchemy-backed implementations of research repositories."""
from __future__ import annotations

from typing import Mapping, Sequence

from sqlalchemy import Text, cast, func
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import (
    NoteEvidence,
    ResearchNote as ResearchNoteModel,
)
from theo.domain.repositories import ResearchNoteRepository
from theo.domain.research import (
    ResearchNote,
    ResearchNoteDraft,
    ResearchNoteEvidence,
    ResearchNoteEvidenceDraft,
    ResearchNoteNotFoundError,
)


def _normalize_tags(tags: tuple[str, ...] | None) -> list[str] | None:
    if tags is None:
        return None
    values = [tag for tag in tags if tag]
    return values or None


def _to_domain_evidence(model: NoteEvidence) -> ResearchNoteEvidence:
    return ResearchNoteEvidence(
        id=model.id,
        source_type=model.source_type,
        source_ref=model.source_ref,
        osis_refs=tuple(model.osis_refs) if model.osis_refs else None,
        citation=model.citation,
        snippet=model.snippet,
        meta=model.meta,
    )


def _to_domain_note(model: ResearchNoteModel) -> ResearchNote:
    return ResearchNote(
        id=model.id,
        osis=model.osis,
        body=model.body,
        title=model.title,
        stance=model.stance,
        claim_type=model.claim_type,
        confidence=model.confidence,
        tags=tuple(model.tags) if model.tags else None,
        evidences=tuple(_to_domain_evidence(evidence) for evidence in model.evidences),
        request_id=model.request_id,
        created_by=model.created_by,
        tenant_id=model.tenant_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _apply_changes(model: ResearchNoteModel, changes: Mapping[str, object]) -> None:
    for field, value in changes.items():
        if field == "tags":
            if isinstance(value, (list, tuple)):
                normalized = tuple(str(tag) for tag in value if tag)
            elif value is None:
                normalized = None
            else:
                normalized = None
            model.tags = _normalize_tags(normalized)
        elif field in {"osis", "body", "title", "stance", "claim_type", "confidence"}:
            setattr(model, field, value)


def _replace_evidences(
    session: Session,
    model: ResearchNoteModel,
    evidences: Sequence[ResearchNoteEvidenceDraft] | None,
) -> None:
    if evidences is None:
        return
    model.evidences.clear()
    session.flush()
    for draft in evidences:
        model.evidences.append(
            NoteEvidence(
                source_type=draft.source_type,
                source_ref=draft.source_ref,
                osis_refs=list(draft.osis_refs) if draft.osis_refs else None,
                citation=draft.citation,
                snippet=draft.snippet,
                meta=dict(draft.meta) if draft.meta else None,
            )
        )


class SqlAlchemyResearchNoteRepository(ResearchNoteRepository):
    """Research note repository backed by a SQLAlchemy session."""

    def __init__(self, session: Session):
        self._session = session

    def create(
        self,
        draft: ResearchNoteDraft,
        *,
        commit: bool = True,
    ) -> ResearchNote:
        model = ResearchNoteModel(
            osis=draft.osis,
            body=draft.body,
            title=draft.title,
            stance=draft.stance,
            claim_type=draft.claim_type,
            confidence=draft.confidence,
            tags=_normalize_tags(draft.tags),
            request_id=draft.request_id,
            created_by=draft.end_user_id,
            tenant_id=draft.tenant_id,
        )
        self._session.add(model)
        self._session.flush()

        _replace_evidences(self._session, model, draft.evidences)
        self._session.flush()

        if commit:
            self._session.commit()
            self._session.refresh(model)

        return _to_domain_note(model)

    def preview(self, draft: ResearchNoteDraft) -> ResearchNote:
        transaction = self._session.begin_nested()
        try:
            preview = self.create(draft, commit=False)
            self._session.flush()
        finally:
            if transaction.is_active:
                transaction.rollback()
        return preview

    def list_for_osis(
        self,
        osis: str,
        *,
        stance: str | None = None,
        claim_type: str | None = None,
        tag: str | None = None,
        min_confidence: float | None = None,
    ) -> list[ResearchNote]:
        query = self._session.query(ResearchNoteModel).filter(ResearchNoteModel.osis == osis)

        if stance:
            stance_normalized = stance.lower()
            query = query.filter(
                ResearchNoteModel.stance.is_not(None),
                func.lower(ResearchNoteModel.stance) == stance_normalized,
            )

        if claim_type:
            claim_normalized = claim_type.lower()
            query = query.filter(
                ResearchNoteModel.claim_type.is_not(None),
                func.lower(ResearchNoteModel.claim_type) == claim_normalized,
            )

        if tag:
            tag_pattern = f'%"{tag.lower()}"%'
            query = query.filter(
                ResearchNoteModel.tags.is_not(None),
                func.lower(cast(ResearchNoteModel.tags, Text)).like(tag_pattern),
            )

        if min_confidence is not None:
            query = query.filter(ResearchNoteModel.confidence >= min_confidence)

        notes = query.order_by(ResearchNoteModel.created_at.desc()).all()
        return [_to_domain_note(note) for note in notes]

    def update(
        self,
        note_id: str,
        changes: Mapping[str, object],
        *,
        evidences: Sequence[ResearchNoteEvidenceDraft] | None = None,
    ) -> ResearchNote:
        note = self._session.get(ResearchNoteModel, note_id)
        if note is None:
            raise ResearchNoteNotFoundError(note_id)

        _apply_changes(note, changes)
        _replace_evidences(self._session, note, evidences)

        self._session.commit()
        self._session.refresh(note)
        return _to_domain_note(note)

    def delete(self, note_id: str) -> None:
        note = self._session.get(ResearchNoteModel, note_id)
        if note is None:
            raise ResearchNoteNotFoundError(note_id)
        self._session.delete(note)
        self._session.commit()


class SqlAlchemyResearchNoteRepositoryFactory:
    """Callable factory producing SQLAlchemy research repositories."""

    def __call__(self, session: Session) -> ResearchNoteRepository:
        return SqlAlchemyResearchNoteRepository(session)


__all__ = [
    "SqlAlchemyResearchNoteRepository",
    "SqlAlchemyResearchNoteRepositoryFactory",
]
