"""Tool handlers used by the MCP server integration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.application.facades.research import (
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    get_research_service,
)
from theo.infrastructure.api.app.persistence_models import Passage

from ..models.research import (
    NoteEvidenceCreate,
    ResearchNote as ResearchNoteSchema,
    ResearchNoteCreate,
)


class MCPToolError(ValueError):
    """Raised when a tool payload cannot be fulfilled."""


def _resolve_document_osis(session: Session, document_id: str) -> str | None:
    """Return the dominant OSIS reference associated with a document."""

    statement = select(Passage.osis_ref, Passage.meta).where(
        Passage.document_id == document_id
    )
    rows = session.execute(statement)

    primary: str | None = None
    fallback: str | None = None

    for row in rows:
        osis_ref: str | None = row.osis_ref
        meta: Mapping[str, Any] | None
        if isinstance(row.meta, Mapping):
            meta = row.meta
        else:
            meta = None

        if meta:
            primary_candidate = meta.get("osis_primary")
            if isinstance(primary_candidate, str) and primary_candidate:
                primary = primary_candidate
                break

        if fallback is None and osis_ref:
            fallback = osis_ref

    return primary or fallback


def _to_evidence_drafts(
    evidences: Sequence[NoteEvidenceCreate] | None,
) -> tuple[ResearchNoteEvidenceDraft, ...]:
    if evidences is None:
        return ()

    drafts: list[ResearchNoteEvidenceDraft] = []
    for evidence in evidences:
        drafts.append(
            ResearchNoteEvidenceDraft(
                source_type=evidence.source_type,
                source_ref=evidence.source_ref,
                osis_refs=tuple(evidence.osis_refs or []) or None,
                citation=evidence.citation,
                snippet=evidence.snippet,
                meta=evidence.meta,
            )
        )
    return tuple(drafts)


def handle_note_write(
    session: Session, payload: Mapping[str, Any]
) -> ResearchNoteSchema:
    """Persist or preview a research note for the MCP `note_write` tool."""

    try:
        note_payload = ResearchNoteCreate.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - defensive guard
        raise MCPToolError(str(exc)) from exc

    osis = (note_payload.osis or "").strip()
    doc_id = payload.get("doc_id")

    if not osis and isinstance(doc_id, str):
        resolved = _resolve_document_osis(session, doc_id)
        if resolved:
            osis = resolved

    if not osis:
        raise MCPToolError("note_write payload must include an OSIS reference")

    commit_flag = payload.get("commit")
    commit = True if commit_flag is None else bool(commit_flag)

    service = get_research_service(session)
    draft = ResearchNoteDraft(
        osis=osis,
        body=note_payload.body,
        title=note_payload.title,
        stance=note_payload.stance,
        claim_type=note_payload.claim_type,
        tags=tuple(note_payload.tags or []) or None,
        evidences=_to_evidence_drafts(note_payload.evidences),
    )

    if commit:
        note = service.create_note(draft, commit=True)
        return ResearchNoteSchema.model_validate(note)

    preview = service.preview_note(draft)
    return preview


__all__ = ["handle_note_write", "MCPToolError"]
