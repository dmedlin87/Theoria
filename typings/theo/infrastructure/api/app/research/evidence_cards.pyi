from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.orm import Session


class EvidenceCard:
    id: str | None


def create_evidence_card(
    session: Session,
    *,
    osis: str,
    claim_summary: str,
    evidence: Mapping[str, Any] | str,
    tags: Sequence[str] | None,
    commit: bool,
    request_id: str,
    end_user_id: str,
    tenant_id: str | None,
) -> EvidenceCard: ...


def preview_evidence_card(
    session: Session,
    *,
    osis: str,
    claim_summary: str,
    evidence: Mapping[str, Any] | str,
    tags: Sequence[str] | None,
) -> Mapping[str, Any]: ...


__all__ = [
    "EvidenceCard",
    "create_evidence_card",
    "preview_evidence_card",
]
