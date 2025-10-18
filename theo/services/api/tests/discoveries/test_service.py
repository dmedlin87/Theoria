"""Tests for :mod:`theo.services.api.app.discoveries.service`."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure that any stubbed module from other tests is removed before import.
sys.modules.pop("theo.services.api.app.discoveries", None)
sys.modules.pop("theo.services.api.app.discoveries.service", None)
sys.modules.pop("theo.services.api.app.discoveries.tasks", None)

from theo.adapters.persistence.models import (  # noqa: E402 - imported after cleanup
    Base,
    CorpusSnapshot,
    Discovery,
    Document,
    Passage,
)
from theo.domain.discoveries import CorpusSnapshotSummary, DiscoveryType
from theo.services.api.app.discoveries.service import DiscoveryService  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


class _RecordingPatternEngine:
    def __init__(self, candidates, snapshot):
        self.candidates = candidates
        self.snapshot = snapshot
        self.seen_documents = None

    def detect(self, documents):
        self.seen_documents = documents
        return self.candidates, self.snapshot


class _RecordingTrendEngine:
    history_window = 3

    def __init__(self, candidates):
        self.candidates = candidates
        self.seen_snapshots = None

    def detect(self, snapshots):
        self.seen_snapshots = snapshots
        return self.candidates


class _RecordingListEngine:
    def __init__(self, candidates):
        self.candidates = candidates
        self.seen_documents = None

    def detect(self, documents):
        self.seen_documents = documents
        return self.candidates


@pytest.fixture
def seeded_session(session: Session) -> Session:
    user_id = "user-123"
    primary_document = Document(
        id="doc-primary",
        collection=user_id,
        title=None,
        abstract="A thoughtful exploration of key themes.",
        topics=[
            "  Spiritual Growth  ",
            {"label": "  Redemption  "},
            {"topic": "  Charity  "},
            "",
            {"name": "  Service  "},
        ],
    )
    secondary_document = Document(
        id="doc-empty",
        collection=user_id,
        title="  Secondary Title  ",
        abstract=None,
        topics=["  Secondary  "],
    )
    session.add_all([primary_document, secondary_document])

    session.add_all(
        [
            Passage(
                document_id="doc-primary",
                text="content",
                embedding=[0.2, 0.4, 0.6],
                osis_verse_ids=[5, 2, 5],
            ),
            Passage(
                document_id="doc-primary",
                text="content",
                embedding=[float("nan"), 0.8, 0.9],
                osis_verse_ids=[3],
            ),
            Passage(
                document_id="doc-primary",
                text="content",
                embedding=[0.0, 0.1, 0.2],
                osis_verse_ids=[7, 1],
            ),
            Passage(
                document_id="doc-empty",
                text="content",
                embedding=[],
                osis_verse_ids=[9],
            ),
        ]
    )

    stale_discovery = Discovery(
        user_id=user_id,
        discovery_type=DiscoveryType.PATTERN.value,
        title="Old",
        description="stale",
        confidence=0.1,
        relevance_score=0.2,
        viewed=True,
        meta={"legacy": True},
    )
    session.add(stale_discovery)
    session.commit()
    return session


def _build_service(session: Session):
    pattern_candidates = [
        SimpleNamespace(
            title="Pattern Candidate",
            description="A repeating observation",
            confidence=0.91,
            relevance_score=0.83,
            metadata={"pattern": "emerging"},
        )
    ]
    snapshot = CorpusSnapshotSummary(
        snapshot_date=datetime(2024, 1, 1, tzinfo=UTC),
        document_count=3,
        verse_coverage={"Psalms": 5},
        dominant_themes={"Grace": 0.7},
        metadata={"window": "Q1"},
    )
    pattern_engine = _RecordingPatternEngine(pattern_candidates, snapshot)

    contradiction_candidates = [
        SimpleNamespace(
            title="Contradiction Candidate",
            description="Conflicting claims",
            confidence=0.5,
            relevance_score=0.65,
            document_a_id="doc-primary",
            document_b_id="doc-other",
            document_a_title="Primary",
            document_b_title="Other",
            claim_a="Claim A",
            claim_b="Claim B",
            contradiction_type="logical",
            metadata={"strength": "high"},
        )
    ]
    contradiction_engine = _RecordingListEngine(contradiction_candidates)

    trend_candidates = [
        SimpleNamespace(
            title="Trend Candidate",
            description="Trending themes",
            confidence=0.71,
            relevance_score=0.79,
            metadata={"trend": "increasing"},
        )
    ]
    trend_engine = _RecordingTrendEngine(trend_candidates)

    anomaly_candidates = [
        SimpleNamespace(
            title="Anomaly Candidate",
            description="Unexpected spike",
            confidence=0.61,
            relevance_score=0.52,
            document_id="doc-primary",
            anomaly_score=0.44,
            metadata={"flagged": True},
        )
    ]
    anomaly_engine = _RecordingListEngine(anomaly_candidates)

    connection_candidates = [
        SimpleNamespace(
            title="Connection Candidate",
            description="Linked insights",
            confidence=0.58,
            relevance_score=0.6,
            metadata={"connection": "shared"},
        )
    ]
    connection_engine = _RecordingListEngine(connection_candidates)

    gap_candidates = [
        SimpleNamespace(
            title="Gap Candidate",
            description="Missing coverage",
            confidence=0.64,
            relevance_score=0.55,
            reference_topic="Service",
            missing_keywords=("mercy", "justice"),
            shared_keywords=("grace",),
            related_documents=("doc-primary",),
            metadata={"gap": "needs attention"},
        )
    ]
    gap_engine = _RecordingListEngine(gap_candidates)

    service = DiscoveryService(
        session,
        pattern_engine=pattern_engine,
        contradiction_engine=contradiction_engine,
        trend_engine=trend_engine,
        anomaly_engine=anomaly_engine,
        connection_engine=connection_engine,
        gap_engine=gap_engine,
    )
    return (
        service,
        pattern_engine,
        contradiction_engine,
        trend_engine,
        anomaly_engine,
        connection_engine,
        gap_engine,
    )


def test_refresh_user_discoveries_creates_records(seeded_session: Session):
    (
        service,
        pattern_engine,
        contradiction_engine,
        trend_engine,
        anomaly_engine,
        connection_engine,
        gap_engine,
    ) = _build_service(seeded_session)

    results = service.refresh_user_discoveries("user-123")

    assert [item.title for item in results] == [
        "Pattern Candidate",
        "Contradiction Candidate",
        "Trend Candidate",
        "Anomaly Candidate",
        "Connection Candidate",
        "Gap Candidate",
    ]

    documents = pattern_engine.seen_documents
    assert documents is not None
    assert [doc.document_id for doc in documents] == ["doc-primary"]
    primary = documents[0]
    assert primary.title == "Untitled Document"
    assert primary.topics == [
        "Spiritual Growth",
        "Redemption",
        "Charity",
        "Service",
    ]
    assert primary.verse_ids == [1, 2, 3, 5, 7]
    expected_embedding = np.mean([[0.2, 0.4, 0.6], [0.0, 0.1, 0.2]], axis=0).tolist()
    assert primary.embedding == pytest.approx(expected_embedding)

    assert contradiction_engine.seen_documents is documents
    assert anomaly_engine.seen_documents is documents
    assert connection_engine.seen_documents is documents
    assert gap_engine.seen_documents is documents
    assert trend_engine.seen_snapshots[0].document_count == 3
    assert trend_engine.seen_snapshots[-1].metadata == {"window": "Q1"}

    stale = (
        seeded_session.execute(select(Discovery).where(Discovery.title == "Old"))
        .scalars()
        .first()
    )
    assert stale is None

    persisted = (
        seeded_session.execute(select(Discovery).where(Discovery.user_id == "user-123"))
        .scalars()
        .all()
    )
    assert len(persisted) == 6
    assert {record.discovery_type for record in persisted} == {
        DiscoveryType.PATTERN.value,
        DiscoveryType.CONTRADICTION.value,
        DiscoveryType.TREND.value,
        DiscoveryType.ANOMALY.value,
        DiscoveryType.CONNECTION.value,
        DiscoveryType.GAP.value,
    }
    for record in persisted:
        assert record.created_at is not None
        assert record.meta

    snapshots = seeded_session.execute(select(CorpusSnapshot)).scalars().all()
    assert len(snapshots) == 1
    snapshot_row = snapshots[0]
    assert snapshot_row.document_count == 3
    assert snapshot_row.meta == {"window": "Q1"}


def test_average_vectors_filters_non_finite():
    vectors = [
        [0.0, 1.0],
        [float("nan"), 3.0],
        [float("inf"), 5.0],
        [2.0, 3.0],
    ]
    result = DiscoveryService._average_vectors(vectors)
    assert result == [1.0, 2.0]
