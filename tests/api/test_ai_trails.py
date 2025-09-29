"""Regression tests for agent trail persistence."""
from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.ai.trails import TrailService
from theo.services.api.app.core.database import Base
from theo.services.api.app.db.models import AgentTrail


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db_session = TestingSession()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_trail_recorder_persists_retrieval_snapshots(session: Session) -> None:
    service = TrailService(session)

    with service.start_trail(
        workflow="chat",
        plan_md=None,
        mode="guided",
        input_payload={"question": "What is John 1:1?"},
        user_id="tester",
    ) as recorder:
        step = recorder.log_step(
            tool="llm.generate",
            action="compose",
            input_payload={"prompt": "answer"},
            output_payload={"completion": "Answer"},
        )
        recorder.record_retrieval_snapshot(
            retrieval_hash="abc123",
            passage_ids=["passage-1", "passage-2"],
            osis_refs=["John.1.1", "John.1.2"],
            step=step,
        )
        trail_id = recorder.trail.id
        recorder.finalize(
            final_md="# Summary", output_payload={"answer": {"summary": "Answer"}}
        )

    session.expire_all()
    stored_trail = service.get_trail(trail_id)
    assert stored_trail is not None
    assert stored_trail.retrieval_snapshots
    snapshot = stored_trail.retrieval_snapshots[0]
    assert snapshot.retrieval_hash == "abc123"
    assert snapshot.turn_index == 0
    assert snapshot.passage_ids == ["passage-1", "passage-2"]
    assert snapshot.osis_refs == ["John.1.1", "John.1.2"]
    assert snapshot.step_id == step.id


def test_trail_replay_retains_retrieval_snapshots(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = TrailService(session)

    with service.start_trail(
        workflow="verse_copilot",
        plan_md="Plan",
        mode="guided",
        input_payload={"osis": "John.1.1"},
        user_id="tester",
    ) as recorder:
        step = recorder.log_step(tool="rag.compose", output_payload={"summary": "Initial"})
        recorder.record_retrieval_snapshot(
            retrieval_hash="digest-1",
            passage_ids=["passage-42"],
            osis_refs=["John.1.1"],
            step=step,
        )
        trail_id = recorder.trail.id
        recorder.finalize(
            final_md="Plan complete", output_payload={"answer": {"summary": "Initial"}}
        )

    session.expire_all()
    trail = session.get(AgentTrail, trail_id)
    assert trail is not None
    assert len(trail.retrieval_snapshots) == 1

    monkeypatch.setattr(
        TrailService,
        "_replay_verse_copilot",
        lambda self, payload: {"answer": {"summary": "Updated", "citations": []}},
    )

    result = service.replay_trail(trail)
    assert result.output == {"answer": {"summary": "Updated", "citations": []}}

    session.refresh(trail)
    assert len(trail.retrieval_snapshots) == 1
    assert trail.retrieval_snapshots[0].retrieval_hash == "digest-1"
