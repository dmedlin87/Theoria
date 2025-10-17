"""SQLAlchemy-backed repository for hypotheses."""

from collections.abc import Mapping
from typing import Sequence

from sqlalchemy import Text, cast, func
from sqlalchemy.orm import Session

from theo.domain.research import Hypothesis, HypothesisDraft, HypothesisNotFoundError
from theo.domain.repositories import HypothesisRepository
from theo.adapters.persistence.models import Hypothesis as HypothesisModel


def _normalize_list(values: Sequence[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = [value for value in (str(item).strip() for item in values) if value]
    return cleaned or None


def _to_domain(model: HypothesisModel) -> Hypothesis:
    perspective = (
        {str(key): float(val) for key, val in model.perspective_scores.items()}
        if model.perspective_scores
        else None
    )
    metadata = dict(model.details) if model.details else None

    return Hypothesis(
        id=model.id,
        claim=model.claim,
        confidence=model.confidence,
        status=model.status,
        trail_id=model.trail_id,
        supporting_passage_ids=tuple(model.supporting_passage_ids or []),
        contradicting_passage_ids=tuple(model.contradicting_passage_ids or []),
        perspective_scores=perspective,
        metadata=metadata,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _apply_changes(model: HypothesisModel, changes: Mapping[str, object]) -> None:
    for field, value in changes.items():
        if field in {"claim", "status"} and isinstance(value, str):
            setattr(model, field, value.strip())
        elif field == "confidence" and isinstance(value, (int, float)):
            model.confidence = float(value)
        elif field == "trail_id":
            model.trail_id = str(value) if value is not None else None
        elif field == "supporting_passage_ids":
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                model.supporting_passage_ids = _normalize_list(value)
            elif value is None:
                model.supporting_passage_ids = None
        elif field == "contradicting_passage_ids":
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                model.contradicting_passage_ids = _normalize_list(value)
            elif value is None:
                model.contradicting_passage_ids = None
        elif field == "perspective_scores" and isinstance(value, Mapping):
            normalized = {
                str(key): float(val) for key, val in value.items() if isinstance(val, (int, float))
            }
            model.perspective_scores = normalized or None
        elif field == "metadata" and isinstance(value, Mapping):
            mapped = dict(value)
            model.details = mapped or None
        elif field == "metadata" and value is None:
            model.details = None


class SqlAlchemyHypothesisRepository(HypothesisRepository):
    """Hypothesis repository backed by SQLAlchemy sessions."""

    def __init__(self, session: Session):
        self._session = session

    def create(self, draft: HypothesisDraft, *, commit: bool = True) -> Hypothesis:
        perspective_scores = (
            {str(key): float(val) for key, val in draft.perspective_scores.items()}
            if draft.perspective_scores
            else None
        )
        metadata = dict(draft.metadata) if draft.metadata else None

        model = HypothesisModel(
            claim=draft.claim.strip(),
            confidence=float(draft.confidence),
            status=draft.status.strip(),
            trail_id=draft.trail_id,
            supporting_passage_ids=_normalize_list(draft.supporting_passage_ids),
            contradicting_passage_ids=_normalize_list(draft.contradicting_passage_ids),
            perspective_scores=perspective_scores,
            details=metadata,
        )
        self._session.add(model)
        self._session.flush()

        if commit:
            self._session.commit()
            self._session.refresh(model)

        return _to_domain(model)

    def list(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
        min_confidence: float | None = None,
        query: str | None = None,
    ) -> list[Hypothesis]:
        stmt = self._session.query(HypothesisModel)

        if statuses:
            lowered = {status.lower() for status in statuses if status}
            if lowered:
                stmt = stmt.filter(func.lower(HypothesisModel.status).in_(lowered))

        if min_confidence is not None:
            stmt = stmt.filter(HypothesisModel.confidence >= min_confidence)

        if query:
            pattern = f"%{query.lower()}%"
            stmt = stmt.filter(
                func.lower(cast(HypothesisModel.claim, Text)).like(pattern)
            )

        results = stmt.order_by(HypothesisModel.updated_at.desc()).all()
        return [_to_domain(model) for model in results]

    def update(self, hypothesis_id: str, changes: Mapping[str, object]) -> Hypothesis:
        model = self._session.get(HypothesisModel, hypothesis_id)
        if model is None:
            raise HypothesisNotFoundError(hypothesis_id)

        _apply_changes(model, changes)
        self._session.commit()
        self._session.refresh(model)
        return _to_domain(model)


class SqlAlchemyHypothesisRepositoryFactory:
    """Factory producing repository instances per-session."""

    def __call__(self, session: Session) -> HypothesisRepository:  # pragma: no cover - trivial
        return SqlAlchemyHypothesisRepository(session)


__all__ = [
    "SqlAlchemyHypothesisRepository",
    "SqlAlchemyHypothesisRepositoryFactory",
]
