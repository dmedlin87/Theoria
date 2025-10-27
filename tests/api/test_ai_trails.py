"""Regression tests for agent trail persistence."""
from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
import time
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.infrastructure.api.app.ai.trails import TrailService, TrailStepDigest
from theo.application.facades.database import Base
from theo.adapters.persistence.models import AgentTrail, ChatSession
from theo.infrastructure.api.app.models.ai import ChatGoalState, ChatMemoryEntry
from tests.utils.query_profiler import before_cursor_execute, after_cursor_execute, print_query_profile

query_data = {"queries": [], "total_time": 0}

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


def test_trail_digest_persists_chat_memory(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = TrailService(session)
    recorded_tasks: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        "theo.infrastructure.api.app.ai.trails_memory_bridge.celery",
        SimpleNamespace(
            send_task=lambda name, kwargs=None, args=None: recorded_tasks.append(
                (name, kwargs or {})
            )
        ),
    )

    with service.start_trail(
        workflow="chat",
        plan_md="Plan",
        mode="chat",
        input_payload={
            "session_id": "chat-session-1",
            "messages": [{"role": "user", "content": "What does John 1 teach?"}],
            "filters": {},
        },
        user_id="tester",
    ) as recorder:
        digest = TrailStepDigest(
            summary="The prologue affirms Christ's divinity.",
            key_entities=["John 1:1 - Logos"],
            recommended_actions=["Review commentary on John 1"],
        )
        recorder.log_step(
            tool="rag.compose",
            output_payload={"answer": {"summary": digest.summary}},
            digest=digest,
            significant=True,
        )
        trail_id = recorder.trail.id
        recorder.finalize(final_md=digest.summary, output_payload={"answer": {"summary": digest.summary}})

    session.expire_all()
    chat_session = session.get(ChatSession, "chat-session-1")
    assert chat_session is not None
    assert chat_session.summary.startswith("The prologue")
    assert len(chat_session.memory_snippets) == 1
    entry = ChatMemoryEntry.model_validate(chat_session.memory_snippets[0])
    assert entry.trail_id == trail_id
    assert entry.digest_hash is not None
    assert entry.key_entities == ["John 1:1 - Logos"]
    assert entry.recommended_actions == ["Review commentary on John 1"]

    assert recorded_tasks == [
        (
            "tasks.enqueue_follow_up_retrieval",
            {"session_id": "chat-session-1", "trail_id": trail_id, "action": "Review commentary on John 1"},
        )
    ]


def test_trail_digest_updates_goal_progress(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = TrailService(session)
    recorded_tasks: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        "theo.infrastructure.api.app.ai.trails_memory_bridge.celery",
        SimpleNamespace(
            send_task=lambda name, kwargs=None, args=None: recorded_tasks.append(
                (name, kwargs or {})
            )
        ),
    )

    with service.start_trail(
        workflow="chat",
        plan_md="Plan",
        mode="chat",
        input_payload={
            "session_id": "chat-session-goal",
            "messages": [{"role": "user", "content": "Track resurrection harmonisation"}],
            "filters": {},
        },
        user_id="tester",
    ) as recorder:
        now = datetime.now(UTC)
        previous_interaction = now - timedelta(hours=1)
        goal = ChatGoalState(
            id="goal-harmonise",
            title="Harmonise resurrection narratives",
            trail_id=recorder.trail.id,
            status="active",
            priority=0,
            summary="Previous insight",
            created_at=now - timedelta(days=1),
            updated_at=previous_interaction,
            last_interaction_at=previous_interaction,
        )
        chat_session = ChatSession(
            id="chat-session-goal",
            user_id="tester",
            stance="chat",
            summary="Previous insight",
            memory_snippets=[],
            document_ids=[],
            goals=[goal.model_dump(mode="json")],
            preferences=None,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(hours=1),
            last_interaction_at=now - timedelta(hours=1),
        )
        session.add(chat_session)
        session.flush()

        digest = TrailStepDigest(
            summary="New census discovery ties into resurrection timeline.",
            key_entities=["Roman census"],
            recommended_actions=["Compare census records"]
        )
        recorder.log_step(
            tool="rag.compose",
            output_payload={"answer": {"summary": digest.summary}},
            digest=digest,
            significant=True,
        )
        trail_id = recorder.trail.id
        recorder.finalize(
            final_md=digest.summary,
            output_payload={"answer": {"summary": digest.summary}},
        )

    session.expire_all()
    chat_session = session.get(ChatSession, "chat-session-goal")
    assert chat_session is not None
    assert chat_session.summary.startswith("New census discovery")
    assert len(chat_session.memory_snippets) == 1
    entry = ChatMemoryEntry.model_validate(chat_session.memory_snippets[0])
    assert entry.trail_id == trail_id
    assert entry.goal_id == "goal-harmonise"
    assert entry.goal_ids == ["goal-harmonise"]

    stored_goal = ChatGoalState.model_validate(chat_session.goals[0])
    assert stored_goal.summary == "New census discovery ties into resurrection timeline."
    assert stored_goal.last_interaction_at > previous_interaction
    assert stored_goal.updated_at == stored_goal.last_interaction_at

    assert recorded_tasks == [
        (
            "tasks.enqueue_follow_up_retrieval",
            {
                "session_id": "chat-session-goal",
                "trail_id": trail_id,
                "action": "Compare census records",
            },
        )
    ]


def test_trail_digest_deduplicates_entries(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    event.listen(Engine, "before_cursor_execute", before_cursor_execute)
    event.listen(Engine, "after_cursor_execute", after_cursor_execute)

    service = TrailService(session)
    recorded_tasks: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        "theo.infrastructure.api.app.ai.trails_memory_bridge.celery",
        SimpleNamespace(
            send_task=lambda name, kwargs=None, args=None: recorded_tasks.append(
                (name, kwargs or {})
            )
        ),
    )

    with service.start_trail(
        workflow="chat",
        plan_md="Plan",
        mode="chat",
        input_payload={
            "session_id": "chat-session-2",
            "messages": [{"role": "user", "content": "Summarise Romans 8"}],
            "filters": {},
        },
        user_id="tester",
    ) as recorder:
        digest = TrailStepDigest(
            summary="Romans 8 celebrates life in the Spirit.",
            key_entities=["Romans 8:1"],
            recommended_actions=["Explore cross references"],
        )
        recorder.log_step(
            tool="rag.compose",
            output_payload={"answer": {"summary": digest.summary}},
            digest=digest,
            significant=True,
        )
        recorder.log_step(
            tool="rag.compose",
            output_payload={"answer": {"summary": digest.summary}},
            digest=digest,
            significant=True,
        )
        recorder.finalize(final_md=digest.summary, output_payload={"answer": {"summary": digest.summary}})

    session.expire_all()
    chat_session = session.get(ChatSession, "chat-session-2")
    assert chat_session is not None
    assert len(chat_session.memory_snippets) == 1
    entry = ChatMemoryEntry.model_validate(chat_session.memory_snippets[0])
    assert entry.answer_summary == "Romans 8 celebrates life in the Spirit."
    assert entry.recommended_actions == ["Explore cross references"]
    assert recorded_tasks == [
        (
            "tasks.enqueue_follow_up_retrieval",
            {
                "session_id": "chat-session-2",
                "trail_id": entry.trail_id,
                "action": "Explore cross references",
            },
        )
    ]

    print_query_profile()
