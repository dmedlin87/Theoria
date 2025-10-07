"""Persistence helpers for MCP-authored evidence cards."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from ..db.models import EvidenceCard


def _normalize_tags(tags: Iterable[str] | None) -> list[str] | None:
    if tags is None:
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            continue
        stripped = tag.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower in seen:
            continue
        seen.add(lower)
        normalized.append(stripped)
    return sorted(normalized) if normalized else None


def create_evidence_card(
    session: Session,
    *,
    osis: str,
    claim_summary: str,
    evidence: dict[str, Any],
    tags: Iterable[str] | None = None,
    commit: bool = True,
    request_id: str | None = None,
    end_user_id: str | None = None,
    tenant_id: str | None = None,
) -> EvidenceCard:
    """Persist a new evidence card record."""

    card = EvidenceCard(
        osis=osis,
        claim_summary=claim_summary.strip(),
        evidence=dict(evidence),
        tags=_normalize_tags(tags),
        request_id=request_id,
        created_by=end_user_id,
        tenant_id=tenant_id,
    )
    session.add(card)
    session.flush()

    if commit:
        session.commit()
        session.refresh(card)
    return card


def preview_evidence_card(
    session: Session,
    *,
    osis: str,
    claim_summary: str,
    evidence: dict[str, Any],
    tags: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return a preview payload without persisting the evidence card."""

    transaction = session.begin_nested()
    try:
        card = create_evidence_card(
            session,
            osis=osis,
            claim_summary=claim_summary,
            evidence=evidence,
            tags=tags,
            commit=False,
        )
        session.flush()
        preview = {
            "osis": card.osis,
            "claim_summary": card.claim_summary,
            "evidence": card.evidence,
            "tags": card.tags or [],
        }
    finally:
        if transaction.is_active:
            transaction.rollback()
    return preview


__all__ = ["create_evidence_card", "preview_evidence_card"]
