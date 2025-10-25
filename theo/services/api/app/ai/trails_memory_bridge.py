"""Bridge emitting chat memories from trail digests."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from sqlalchemy.orm import Session

from theo.services.api.app.persistence_models import AgentTrail, ChatSession

from ..models.ai import (
    ChatGoalState,
    ChatMemoryEntry,
    ChatSessionMessage,
    ChatSessionPreferences,
)
from .trails import TrailStepDigest

LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover - typing support only
    from celery import Celery


_celery_app: "Celery" | None = None


def _resolve_celery() -> "Celery" | None:
    global _celery_app
    if _celery_app is not None:
        return _celery_app
    try:
        from ..workers.tasks import celery as celery_app
    except Exception:  # pragma: no cover - defensive import guard
        LOGGER.debug("Unable to import celery application", exc_info=True)
        return None
    _celery_app = celery_app
    return _celery_app


class TrailsMemoryBridge:
    """Persist structured trail digests into chat session memory."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record_digest(
        self,
        *,
        trail: AgentTrail,
        step: Any,
        digest: TrailStepDigest,
    ) -> None:
        _ = step  # Step metadata is currently unused but kept for API parity.
        session_id = self._extract_session_id(trail)
        if not session_id:
            return

        question = self._extract_latest_question(trail)
        if not question:
            question = f"Research update from {trail.workflow}".strip()

        prompt_hint = self._build_prompt_hint(digest)
        message_text = self._compose_message_text(digest)

        try:
            from ..ai.rag import RAGAnswer
            from ..routes.ai.workflows import chat as chat_workflow
        except Exception:  # pragma: no cover - defensive import guard
            LOGGER.debug("Unable to load chat workflow helpers", exc_info=True)
            return

        existing = self._session.get(ChatSession, session_id)
        entries = chat_workflow._load_memory_entries(existing)
        digest_hash = digest.digest_hash()
        if any(entry.digest_hash == digest_hash for entry in entries):
            LOGGER.debug(
                "Skipping duplicate digest for session %s", session_id
            )
            return

        truncate = chat_workflow._truncate_text
        text_limit = chat_workflow._MEMORY_TEXT_LIMIT
        summary_limit = chat_workflow._MEMORY_SUMMARY_LIMIT

        truncated_question = truncate(question, text_limit)
        truncated_message = truncate(message_text, text_limit)
        truncated_prompt = truncate(prompt_hint, text_limit) if prompt_hint else None
        truncated_summary = truncate(digest.summary, summary_limit)

        entry = ChatMemoryEntry(
            question=truncated_question,
            answer=truncated_message,
            prompt=truncated_prompt,
            answer_summary=truncated_summary,
            citations=[],
            document_ids=[],
            created_at=datetime.now(UTC),
            trail_id=trail.id,
            digest_hash=digest_hash,
            key_entities=digest.normalised_key_entities(),
            recommended_actions=digest.normalised_recommended_actions(),
        )

        answer = RAGAnswer(
            summary=digest.summary,
            citations=[],
            model_name="trail.digest",
            model_output=message_text,
        )
        message = ChatSessionMessage(role="assistant", content=truncated_message)

        preferences = self._resolve_preferences(existing, trail)

        goals = chat_workflow._load_goal_entries(existing)
        active_goal = self._resolve_trail_goal(trail, goals)
        if active_goal is not None:
            if not entry.goal_id:
                entry.goal_id = active_goal.id
            if entry.goal_ids:
                if active_goal.id not in entry.goal_ids:
                    entry.goal_ids.append(active_goal.id)
            else:
                entry.goal_ids = [active_goal.id]

        chat_workflow._persist_chat_session(
            self._session,
            existing=existing,
            session_id=session_id,
            user_id=trail.user_id,
            stance=trail.mode,
            question=truncated_question,
            prompt=truncated_prompt,
            intent_tags=None,
            message=message,
            answer=answer,
            preferences=preferences,
            goals=goals,
            active_goal=active_goal,
            memory_entry=entry,
        )

        self._schedule_follow_up_retrievals(session_id, trail, digest)

    def _extract_session_id(self, trail: AgentTrail) -> str | None:
        payload = trail.input_payload
        if isinstance(payload, Mapping):
            session_id = payload.get("session_id")
            if isinstance(session_id, str) and session_id.strip():
                return session_id.strip()
        return None

    def _extract_latest_question(self, trail: AgentTrail) -> str | None:
        payload = trail.input_payload
        if not isinstance(payload, Mapping):
            return None
        messages = payload.get("messages")
        if isinstance(messages, Sequence):
            for raw in reversed(messages):
                if not isinstance(raw, Mapping):
                    continue
                if raw.get("role") != "user":
                    continue
                content = raw.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        question = payload.get("question")
        if isinstance(question, str) and question.strip():
            return question.strip()
        return None

    def _build_prompt_hint(self, digest: TrailStepDigest) -> str | None:
        actions = digest.normalised_recommended_actions()
        if not actions:
            return None
        return "Next steps: " + "; ".join(actions)

    def _compose_message_text(self, digest: TrailStepDigest) -> str:
        lines = [digest.summary.strip()]
        entities = digest.normalised_key_entities()
        if entities:
            lines.append("Key entities: " + ", ".join(entities))
        actions = digest.normalised_recommended_actions()
        if actions:
            lines.append("Recommended actions: " + "; ".join(actions))
        return "\n".join(line for line in lines if line).strip()

    def _resolve_preferences(
        self, existing: ChatSession | None, trail: AgentTrail
    ) -> ChatSessionPreferences:
        if existing and existing.preferences:
            try:
                return ChatSessionPreferences.model_validate(existing.preferences)
            except Exception:  # pragma: no cover - fallback to defaults
                LOGGER.debug(
                    "Unable to parse stored preferences for session %s", existing.id, exc_info=True
                )
        mode_hint = trail.mode or trail.workflow
        return ChatSessionPreferences(mode=mode_hint)

    def _schedule_follow_up_retrievals(
        self, session_id: str, trail: AgentTrail, digest: TrailStepDigest
    ) -> None:
        actions = digest.normalised_recommended_actions()
        if not actions:
            return
        celery_app = _resolve_celery()
        if celery_app is None:
            return

        for action in actions:
            try:
                celery_app.send_task(
                    "tasks.enqueue_follow_up_retrieval",
                    kwargs={
                        "session_id": session_id,
                        "trail_id": trail.id,
                        "action": action,
                    },
                )
            except Exception:  # pragma: no cover - log and continue
                LOGGER.debug(
                    "Failed to enqueue follow-up retrieval", exc_info=True
                )

    def _resolve_trail_goal(
        self, trail: AgentTrail, goals: Sequence[ChatGoalState]
    ) -> ChatGoalState | None:
        trail_id = getattr(trail, "id", None)
        if not isinstance(trail_id, str) or not trail_id.strip():
            return None
        normalised_trail = trail_id.strip().lower()
        for goal in goals:
            candidate = getattr(goal, "trail_id", None)
            if isinstance(candidate, str) and candidate.strip().lower() == normalised_trail:
                return goal
        return None


__all__ = ["TrailsMemoryBridge"]
