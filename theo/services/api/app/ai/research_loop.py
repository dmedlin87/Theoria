"""Research loop orchestrator powering stop/step/pause controls."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from sqlalchemy.orm import Session

from ..models.ai import LoopControlAction, ResearchLoopState, ResearchLoopStatus
from ..persistence_models import ChatSession

DEFAULT_LOOP_STEP_SEQUENCE = [
    "understand",
    "gather",
    "tensions",
    "draft",
    "critique",
    "revise",
    "synthesize",
]

_LOOP_STATE_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = Lock()


def _now() -> datetime:
    return datetime.now(UTC)


def _initial_partial(question: str | None) -> str:
    if not question:
        return "Research loop initialising…"
    trimmed = question.strip()
    if len(trimmed) > 140:
        trimmed = f"{trimmed[:137].rstrip()}…"
    return f"Scoping research focus: {trimmed}"


def _truncate_partial(answer: str | None) -> str | None:
    if not answer:
        return None
    stripped = answer.strip()
    if len(stripped) <= 240:
        return stripped
    return f"{stripped[:237].rstrip()}…"


class ResearchLoopController:
    """Persisted state manager for the Cognitive Scholar research loop."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ #
    # State loading / persistence
    # ------------------------------------------------------------------ #

    def _load_state(self, session_id: str) -> ResearchLoopState | None:
        record = self._session.get(ChatSession, session_id)
        raw_state: dict[str, Any] | None = None
        if record and record.preferences:
            preferences = dict(record.preferences or {})
            raw_state = preferences.get("loop_state")
        if raw_state is None:
            with _CACHE_LOCK:
                cached = _LOOP_STATE_CACHE.get(session_id)
            raw_state = deepcopy(cached) if cached is not None else None
        if raw_state is None:
            return None
        try:
            return ResearchLoopState.model_validate(raw_state)
        except Exception:
            # If state parsing fails, reset to idle snapshot.
            return None

    def get_state(self, session_id: str) -> ResearchLoopState:
        state = self._load_state(session_id)
        if state is not None:
            return state
        return ResearchLoopState(session_id=session_id)

    def require_state(self, session_id: str) -> ResearchLoopState:
        state = self._load_state(session_id)
        if state is None:
            raise LookupError(f"research loop state unavailable for session {session_id}")
        return state

    def _store_state(
        self,
        session_id: str,
        state: ResearchLoopState,
        *,
        commit: bool = False,
    ) -> ResearchLoopState:
        payload = state.model_dump(mode="json", exclude_none=True)
        record = self._session.get(ChatSession, session_id)
        if record is not None:
            preferences = dict(record.preferences or {})
            preferences["loop_state"] = payload
            record.preferences = preferences
            self._session.add(record)
            if commit:
                self._session.commit()
            with _CACHE_LOCK:
                _LOOP_STATE_CACHE.pop(session_id, None)
        else:
            with _CACHE_LOCK:
                _LOOP_STATE_CACHE[session_id] = payload
        return state

    def persist_to_record(self, record: ChatSession) -> ResearchLoopState | None:
        state = self._load_state(record.id)
        if state is None:
            return None
        self._store_state(record.id, state)
        return state

    # ------------------------------------------------------------------ #
    # Initialisation / progress updates
    # ------------------------------------------------------------------ #

    def initialise(
        self,
        session_id: str,
        *,
        question: str | None = None,
        total_steps: int | None = None,
    ) -> ResearchLoopState:
        state = self._load_state(session_id)
        if state is None or state.status == ResearchLoopStatus.IDLE:
            sequence = list(DEFAULT_LOOP_STEP_SEQUENCE)
            if total_steps is not None and total_steps > 0:
                sequence = sequence[:total_steps]
            total = len(sequence)
            metadata = {"step_sequence": sequence}
            if question:
                metadata["question"] = question
            state = ResearchLoopState(
                session_id=session_id,
                status=ResearchLoopStatus.RUNNING,
                current_step_index=0,
                total_steps=total,
                pending_actions=sequence[1:],
                partial_answer=_initial_partial(question),
                metadata=metadata,
                updated_at=_now(),
            )
            self._store_state(session_id, state)
        return state

    def set_partial_answer(
        self,
        session_id: str,
        partial_answer: str | None,
        *,
        commit: bool = False,
    ) -> ResearchLoopState:
        state = self.initialise(session_id)
        state.partial_answer = _truncate_partial(partial_answer) or partial_answer
        state.updated_at = _now()
        return self._store_state(session_id, state, commit=commit)

    def mark_completed(
        self,
        session_id: str,
        *,
        final_answer: str | None = None,
    ) -> ResearchLoopState:
        state = self.initialise(session_id)
        state.status = ResearchLoopStatus.COMPLETED
        state.last_action = "complete"
        if state.total_steps > 0:
            state.current_step_index = max(state.total_steps - 1, state.current_step_index)
        state.pending_actions = []
        state.partial_answer = _truncate_partial(final_answer) or state.partial_answer
        if final_answer:
            state.metadata["final_answer"] = final_answer
        state.updated_at = _now()
        return self._store_state(session_id, state)

    # ------------------------------------------------------------------ #
    # Control surface actions
    # ------------------------------------------------------------------ #

    def pause(self, session_id: str) -> ResearchLoopState:
        state = self.require_state(session_id)
        state.status = ResearchLoopStatus.PAUSED
        state.last_action = LoopControlAction.PAUSE.value
        state.updated_at = _now()
        return self._store_state(session_id, state, commit=True)

    def resume(self, session_id: str) -> ResearchLoopState:
        state = self.require_state(session_id)
        state.status = ResearchLoopStatus.RUNNING
        state.last_action = LoopControlAction.RESUME.value
        state.updated_at = _now()
        return self._store_state(session_id, state, commit=True)

    def stop(self, session_id: str) -> ResearchLoopState:
        state = self.require_state(session_id)
        state.status = ResearchLoopStatus.STOPPED
        state.last_action = LoopControlAction.STOP.value
        if not state.partial_answer and state.metadata.get("final_answer"):
            state.partial_answer = _truncate_partial(state.metadata.get("final_answer"))
        state.updated_at = _now()
        return self._store_state(session_id, state, commit=True)

    def step(self, session_id: str, step_id: str | None = None) -> ResearchLoopState:
        state = self.require_state(session_id)
        sequence = state.metadata.get("step_sequence", list(DEFAULT_LOOP_STEP_SEQUENCE))
        if isinstance(sequence, list):
            sequence = list(sequence)
        else:
            sequence = list(DEFAULT_LOOP_STEP_SEQUENCE)
        next_index = state.current_step_index + 1
        if step_id:
            try:
                next_index = sequence.index(step_id)
            except ValueError:
                next_index = state.current_step_index + 1
        next_index = min(next_index, max(len(sequence) - 1, 0))
        state.current_step_index = next_index
        state.total_steps = len(sequence)
        state.pending_actions = sequence[next_index + 1 :]
        state.status = (
            ResearchLoopStatus.COMPLETED
            if next_index >= len(sequence) - 1
            else ResearchLoopStatus.RUNNING
        )
        state.last_action = LoopControlAction.STEP.value
        state.updated_at = _now()
        return self._store_state(session_id, state, commit=True)

    def apply_action(
        self,
        session_id: str,
        action: LoopControlAction,
        *,
        step_id: str | None = None,
    ) -> ResearchLoopState:
        if action is LoopControlAction.PAUSE:
            return self.pause(session_id)
        if action is LoopControlAction.RESUME:
            return self.resume(session_id)
        if action is LoopControlAction.STOP:
            return self.stop(session_id)
        if action is LoopControlAction.STEP:
            return self.step(session_id, step_id=step_id)
        raise ValueError(f"Unsupported loop control action: {action}")  # pragma: no cover


__all__ = [
    "DEFAULT_LOOP_STEP_SEQUENCE",
    "ResearchLoopController",
]

