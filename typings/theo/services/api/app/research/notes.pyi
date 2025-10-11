from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session


class ResearchNote:
    id: str | None


class ResearchNotePreview:
    osis: str | None
    title: str | None
    stance: str | None
    claim_type: str | None
    tags: Sequence[str] | None
    body: str | None


def create_research_note(
    session: Session,
    *,
    osis: str,
    body: str,
    title: str | None,
    stance: str | None,
    claim_type: str | None,
    tags: Sequence[str] | None,
    evidences: Sequence[dict[str, Any]] | None,
    commit: bool,
    request_id: str,
    end_user_id: str,
    tenant_id: str | None,
) -> ResearchNote: ...


def generate_research_note_preview(
    session: Session,
    *,
    osis: str,
    body: str,
    title: str | None,
    stance: str | None,
    claim_type: str | None,
    tags: Sequence[str] | None,
    evidences: Sequence[dict[str, Any]] | None,
) -> ResearchNotePreview: ...


__all__ = [
    "ResearchNote",
    "ResearchNotePreview",
    "create_research_note",
    "generate_research_note_preview",
]
