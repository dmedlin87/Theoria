import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence.models import Hypothesis as HypothesisModel
from theo.adapters.research.hypotheses_sqlalchemy import (
    SqlAlchemyHypothesisRepository,
    _apply_changes,
    _normalize_list,
)
from theo.domain.research import HypothesisDraft, HypothesisNotFoundError


class TrackingSession(Session):
    """Session subclass that records commit/flush/refresh calls."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commit_calls = 0
        self.flush_calls = 0
        self.refresh_calls: list[object] = []

    def commit(self) -> None:  # type: ignore[override]
        self.commit_calls += 1
        super().commit()

    def flush(self, objects=None) -> None:  # type: ignore[override]
        self.flush_calls += 1
        super().flush(objects)

    def refresh(self, instance, attribute_names=None, with_for_update=None):  # type: ignore[override]
        self.refresh_calls.append(instance)
        return super().refresh(
            instance,
            attribute_names=attribute_names,
            with_for_update=with_for_update,
        )


@pytest.fixture()
def engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    metadata = MetaData()
    Table("agent_trails", metadata, Column("id", String, primary_key=True))
    metadata.create_all(engine)
    HypothesisModel.__table__.create(engine, checkfirst=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session(engine):
    SessionLocal = sessionmaker(bind=engine, class_=TrackingSession, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_hypothesis(
    session: TrackingSession,
    *,
    claim: str,
    status: str,
    confidence: float,
    updated_at: datetime,
) -> HypothesisModel:
    model = HypothesisModel(
        id=str(uuid.uuid4()),
        claim=claim,
        status=status,
        confidence=confidence,
        supporting_passage_ids=["John 1:1"],
        perspective_scores={"alpha": 0.5},
        details={"topic": "christology"},
        created_at=updated_at,
        updated_at=updated_at,
    )
    session.add(model)
    session.commit()
    return model


def test_create_persists_hypothesis_and_commits(session: TrackingSession):
    repo = SqlAlchemyHypothesisRepository(session)
    draft = HypothesisDraft(
        claim="  The Word became flesh  ",
        confidence=0.75,
        status=" Active ",
        trail_id="trail-1",
        supporting_passage_ids=("  John 1:1  ", ""),
        contradicting_passage_ids=None,
        perspective_scores={"alpha": 0.5, "beta": 1},
        metadata={"foo": "bar"},
    )

    result = repo.create(draft)

    assert result.claim == "The Word became flesh"
    assert result.status == "Active"
    assert result.supporting_passage_ids == ("John 1:1",)
    assert result.perspective_scores == {"alpha": pytest.approx(0.5), "beta": pytest.approx(1.0)}
    assert session.commit_calls == 1
    assert session.flush_calls >= 1
    assert len(session.refresh_calls) == 1

    stored = session.query(HypothesisModel).one()
    assert stored.claim == "The Word became flesh"
    assert stored.details == {"foo": "bar"}


def test_list_filters_by_status_confidence_and_query(session: TrackingSession):
    now = datetime.now(timezone.utc)
    recent = _seed_hypothesis(
        session,
        claim="Incarnation is central to salvation",
        status="active",
        confidence=0.9,
        updated_at=now,
    )
    _seed_hypothesis(
        session,
        claim="Dormant idea about rituals",
        status="dormant",
        confidence=0.95,
        updated_at=now - timedelta(days=1),
    )
    _seed_hypothesis(
        session,
        claim="Another incarnation question",
        status="active",
        confidence=0.55,
        updated_at=now - timedelta(days=2),
    )

    session.commit_calls = 0

    repo = SqlAlchemyHypothesisRepository(session)
    results = repo.list(
        statuses=("ACTIVE", "Dormant"),
        min_confidence=0.6,
        query="incarnation",
    )

    assert [hypothesis.id for hypothesis in results] == [recent.id]
    assert results[0].supporting_passage_ids == ("John 1:1",)


def test_update_applies_changes_and_commits(session: TrackingSession):
    seed = _seed_hypothesis(
        session,
        claim="Original claim",
        status="active",
        confidence=0.4,
        updated_at=datetime.now(timezone.utc) - timedelta(days=3),
    )
    session.commit_calls = 0
    session.refresh_calls = []

    repo = SqlAlchemyHypothesisRepository(session)
    result = repo.update(
        seed.id,
        {
            "claim": "  Renewed claim  ",
            "status": " Dormant ",
            "confidence": 1,
            "trail_id": None,
            "supporting_passage_ids": ("  Rev 21:5  ", ""),
            "contradicting_passage_ids": ("  Acts 2:1  ",),
            "perspective_scores": {"alpha": 2, "gamma": "skip"},
            "metadata": {"foo": "bar"},
        },
    )

    assert session.commit_calls == 1
    assert len(session.refresh_calls) == 1
    assert result.claim == "Renewed claim"
    assert result.status == "Dormant"
    assert result.supporting_passage_ids == ("Rev 21:5",)
    assert result.contradicting_passage_ids == ("Acts 2:1",)
    assert result.perspective_scores == {"alpha": pytest.approx(2.0)}

    refreshed = session.get(HypothesisModel, seed.id)
    assert refreshed.details == {"foo": "bar"}


def test_update_missing_hypothesis_raises(session: TrackingSession):
    repo = SqlAlchemyHypothesisRepository(session)
    with pytest.raises(HypothesisNotFoundError):
        repo.update("missing-id", {"claim": "new"})
    assert session.commit_calls == 0


def test_normalize_list_trims_and_discards_empty_values():
    assert _normalize_list(("  foo  ", "", "bar", "   ")) == ["foo", "bar"]
    assert _normalize_list(None) is None


def test_apply_changes_normalizes_and_casts_values():
    model = HypothesisModel(
        claim="Original",
        confidence=0.25,
        status="active",
        trail_id="trail-42",
        supporting_passage_ids=["Genesis 1:1"],
        contradicting_passage_ids=["Exodus 3:14"],
        perspective_scores={"existing": 0.1},
        details={"existing": "value"},
    )

    _apply_changes(
        model,
        {
            "claim": "  Updated claim  ",
            "status": " Dormant ",
            "confidence": 2,
            "trail_id": 99,
            "supporting_passage_ids": ("  Isa 7:14  ", "  "),
            "contradicting_passage_ids": None,
            "perspective_scores": {"alpha": 1, 2: 0.5, "beta": "skip"},
            "metadata": {"topic": "christology"},
        },
    )

    assert model.claim == "Updated claim"
    assert model.status == "Dormant"
    assert model.confidence == pytest.approx(2.0)
    assert model.trail_id == "99"
    assert model.supporting_passage_ids == ["Isa 7:14"]
    assert model.contradicting_passage_ids is None
    assert model.perspective_scores == {"alpha": 1.0, "2": 0.5}
    assert model.details == {"topic": "christology"}


def test_apply_changes_clears_optional_fields():
    model = HypothesisModel(
        claim="Original",
        confidence=0.25,
        status="active",
        trail_id="trail-42",
        supporting_passage_ids=["Genesis 1:1"],
        contradicting_passage_ids=["Exodus 3:14"],
        perspective_scores={"existing": 0.1},
        details={"existing": "value"},
    )

    _apply_changes(
        model,
        {
            "supporting_passage_ids": None,
            "contradicting_passage_ids": None,
            "metadata": None,
        },
    )

    assert model.supporting_passage_ids is None
    assert model.contradicting_passage_ids is None
    assert model.details is None
