"""Research loop orchestrator powering stop/step/pause controls."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Callable

from sqlalchemy.orm import Session

from ..models.ai import LoopControlAction, ResearchLoopState, ResearchLoopStatus
from ..models.research_plan import (
    ResearchPlan,
    ResearchPlanReorderRequest,
    ResearchPlanStep,
    ResearchPlanStepSkipRequest,
    ResearchPlanStepStatus,
    ResearchPlanStepUpdateRequest,
)
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


DEFAULT_PLAN_LABELS: dict[str, str] = {
    "understand": "Understand question",
    "gather": "Gather evidence",
    "tensions": "Detect tensions",
    "draft": "Draft response",
    "critique": "Critique reasoning",
    "revise": "Revise answer",
    "synthesize": "Synthesize findings",
}


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
    # Plan helpers
    # ------------------------------------------------------------------ #

    def _build_default_plan(self, session_id: str, sequence: list[str]) -> ResearchPlan:
        timestamp = _now()
        steps: list[ResearchPlanStep] = []
        for index, kind in enumerate(sequence):
            step_id = f"{session_id}-{kind}-{index + 1}"
            label = DEFAULT_PLAN_LABELS.get(kind, kind.replace("_", " ").title())
            steps.append(
                ResearchPlanStep(
                    id=step_id,
                    kind=kind,
                    index=index,
                    label=label,
                    status=(
                        ResearchPlanStepStatus.IN_PROGRESS
                        if index == 0
                        else ResearchPlanStepStatus.PENDING
                    ),
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        return ResearchPlan(
            session_id=session_id,
            steps=steps,
            active_step_id=steps[0].id if steps else None,
            updated_at=timestamp,
        )

    def _ensure_metadata(self, state: ResearchLoopState) -> dict[str, Any]:
        if not isinstance(state.metadata, dict):
            state.metadata = {}
        return state.metadata

    def _write_plan(self, state: ResearchLoopState, plan: ResearchPlan) -> None:
        metadata = self._ensure_metadata(state)
        metadata["plan"] = plan.model_dump(mode="json", exclude_none=True)

    def _step_sequence(self, state: ResearchLoopState) -> list[str]:
        metadata = self._ensure_metadata(state)
        raw = metadata.get("step_sequence")
        if isinstance(raw, list) and raw:
            return [str(entry) for entry in raw]
        metadata["step_sequence"] = list(DEFAULT_LOOP_STEP_SEQUENCE)
        return metadata["step_sequence"]

    def _load_plan_from_state(self, state: ResearchLoopState) -> ResearchPlan:
        metadata = self._ensure_metadata(state)
        raw_plan = metadata.get("plan")
        if raw_plan:
            try:
                plan = ResearchPlan.model_validate(raw_plan)
            except Exception:
                plan = self._build_default_plan(state.session_id, self._step_sequence(state))
        else:
            plan = self._build_default_plan(state.session_id, self._step_sequence(state))
        self._write_plan(state, plan)
        return plan

    def _sync_plan_progress(self, state: ResearchLoopState) -> ResearchPlan:
        plan = self._load_plan_from_state(state)
        if not plan.steps:
            return plan

        timestamp = _now()
        mutated = False

        current_index = min(state.current_step_index, max(len(plan.steps) - 1, 0))
        if state.total_steps == 0:
            state.total_steps = len(plan.steps)

        if current_index < len(plan.steps):
            resolved_active_id = plan.steps[current_index].id
        else:
            resolved_active_id = plan.steps[-1].id

        for idx, step in enumerate(plan.steps):
            if step.status in {
                ResearchPlanStepStatus.SKIPPED,
                ResearchPlanStepStatus.BLOCKED,
            }:
                continue

            desired_status = step.status
            if state.status is ResearchLoopStatus.COMPLETED:
                desired_status = ResearchPlanStepStatus.COMPLETED
            elif idx < current_index:
                desired_status = ResearchPlanStepStatus.COMPLETED
            elif idx == current_index:
                if state.status in {
                    ResearchLoopStatus.RUNNING,
                    ResearchLoopStatus.STEPPING,
                    ResearchLoopStatus.PAUSED,
                }:
                    desired_status = ResearchPlanStepStatus.IN_PROGRESS
                elif state.status is ResearchLoopStatus.STOPPED:
                    desired_status = ResearchPlanStepStatus.BLOCKED
                else:
                    desired_status = ResearchPlanStepStatus.PENDING
            else:
                desired_status = (
                    ResearchPlanStepStatus.BLOCKED
                    if state.status is ResearchLoopStatus.STOPPED
                    else ResearchPlanStepStatus.PENDING
                )

            if desired_status != step.status:
                step.status = desired_status
                step.updated_at = timestamp
                mutated = True

        if plan.active_step_id != resolved_active_id:
            plan.active_step_id = resolved_active_id
            mutated = True

        if mutated:
            plan.version += 1
            plan.updated_at = timestamp
            self._write_plan(state, plan)

        return plan

    def _apply_plan_mutation(
        self,
        session_id: str,
        mutator: Callable[[ResearchPlan, ResearchLoopState], bool],
        *,
        commit: bool = False,
    ) -> ResearchPlan:
        state = self.require_state(session_id)
        plan = self._load_plan_from_state(state)
        mutated = mutator(plan, state)
        if mutated:
            plan.version += 1
            plan.updated_at = _now()
            self._write_plan(state, plan)
        self._sync_plan_progress(state)
        updated_state = self._store_state(session_id, state, commit=commit)
        return self._load_plan_from_state(updated_state)

    def get_plan(self, session_id: str) -> ResearchPlan:
        state = self._load_state(session_id)
        if state is None:
            return self._build_default_plan(session_id, list(DEFAULT_LOOP_STEP_SEQUENCE))
        plan = self._load_plan_from_state(state)
        self._sync_plan_progress(state)
        self._store_state(session_id, state)
        return plan

    def reorder_plan(
        self,
        session_id: str,
        payload: ResearchPlanReorderRequest,
    ) -> ResearchPlan:
        def mutate(plan: ResearchPlan, state: ResearchLoopState) -> bool:
            if not payload.order:
                return False
            existing_ids = {step.id for step in plan.steps}
            order_ids = list(dict.fromkeys(payload.order))
            if set(order_ids) != existing_ids:
                raise ValueError("order must contain all existing step identifiers")
            id_to_step = {step.id: step for step in plan.steps}
            timestamp = _now()
            reordered: list[ResearchPlanStep] = []
            for index, step_id in enumerate(order_ids):
                step = id_to_step[step_id]
                if step.index != index:
                    step.index = index
                    step.updated_at = timestamp
                reordered.append(step)
            plan.steps = reordered
            metadata = self._ensure_metadata(state)
            metadata["step_sequence"] = [step.kind for step in plan.steps]
            if plan.active_step_id:
                try:
                    new_index = next(
                        idx for idx, entry in enumerate(plan.steps) if entry.id == plan.active_step_id
                    )
                except StopIteration:
                    new_index = 0
                    plan.active_step_id = plan.steps[0].id if plan.steps else None
                state.current_step_index = new_index
            state.total_steps = len(plan.steps)
            state.pending_actions = metadata["step_sequence"][state.current_step_index + 1 :]
            return True

        return self._apply_plan_mutation(session_id, mutate)

    def update_plan_step(
        self,
        session_id: str,
        step_id: str,
        payload: ResearchPlanStepUpdateRequest,
    ) -> ResearchPlan:
        def mutate(plan: ResearchPlan, _: ResearchLoopState) -> bool:
            step = next((item for item in plan.steps if item.id == step_id), None)
            if step is None:
                raise LookupError(f"plan step {step_id} not found")
            updated = False
            timestamp = _now()
            if payload.query is not None and payload.query != step.query:
                step.query = payload.query
                updated = True
            if payload.tool is not None and payload.tool != step.tool:
                step.tool = payload.tool
                updated = True
            if payload.status is not None and payload.status != step.status:
                step.status = payload.status
                updated = True
            if (
                payload.estimated_tokens is not None
                and payload.estimated_tokens != step.estimated_tokens
            ):
                step.estimated_tokens = payload.estimated_tokens
                updated = True
            if (
                payload.estimated_cost_usd is not None
                and payload.estimated_cost_usd != step.estimated_cost_usd
            ):
                step.estimated_cost_usd = payload.estimated_cost_usd
                updated = True
            if (
                payload.estimated_duration_seconds is not None
                and payload.estimated_duration_seconds != step.estimated_duration_seconds
            ):
                step.estimated_duration_seconds = payload.estimated_duration_seconds
                updated = True
            if payload.metadata is not None:
                step.metadata = payload.metadata
                updated = True
            if updated:
                step.updated_at = timestamp
            return updated

        return self._apply_plan_mutation(session_id, mutate)

    def skip_plan_step(
        self,
        session_id: str,
        step_id: str,
        payload: ResearchPlanStepSkipRequest,
    ) -> ResearchPlan:
        def mutate(plan: ResearchPlan, state: ResearchLoopState) -> bool:
            step = next((item for item in plan.steps if item.id == step_id), None)
            if step is None:
                raise LookupError(f"plan step {step_id} not found")
            if step.status is ResearchPlanStepStatus.SKIPPED:
                return False
            step.status = ResearchPlanStepStatus.SKIPPED
            if payload.reason:
                step.metadata = dict(step.metadata)
                step.metadata["skip_reason"] = payload.reason
            step.updated_at = _now()
            if plan.active_step_id == step.id:
                remaining = [s for s in plan.steps if s.status != ResearchPlanStepStatus.SKIPPED]
                if remaining:
                    plan.active_step_id = remaining[0].id
                    state.current_step_index = next(
                        (
                            idx
                            for idx, item in enumerate(plan.steps)
                            if item.id == plan.active_step_id
                        ),
                        state.current_step_index,
                    )
                else:
                    plan.active_step_id = None
                    state.current_step_index = len(plan.steps) - 1
                    state.status = ResearchLoopStatus.COMPLETED
            metadata = self._ensure_metadata(state)
            sequence = metadata.get("step_sequence", [])
            metadata["step_sequence"] = sequence
            state.pending_actions = sequence[state.current_step_index + 1 :]
            return True

        return self._apply_plan_mutation(session_id, mutate, commit=True)

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
            plan = self._load_plan_from_state(state)
            self._write_plan(state, plan)
            self._sync_plan_progress(state)
            self._store_state(session_id, state)
        else:
            self._sync_plan_progress(state)
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
        self._sync_plan_progress(state)
        return self._store_state(session_id, state)

    # ------------------------------------------------------------------ #
    # Control surface actions
    # ------------------------------------------------------------------ #

    def pause(self, session_id: str) -> ResearchLoopState:
        state = self.require_state(session_id)
        state.status = ResearchLoopStatus.PAUSED
        state.last_action = LoopControlAction.PAUSE.value
        state.updated_at = _now()
        self._sync_plan_progress(state)
        return self._store_state(session_id, state, commit=True)

    def resume(self, session_id: str) -> ResearchLoopState:
        state = self.require_state(session_id)
        state.status = ResearchLoopStatus.RUNNING
        state.last_action = LoopControlAction.RESUME.value
        state.updated_at = _now()
        self._sync_plan_progress(state)
        return self._store_state(session_id, state, commit=True)

    def stop(self, session_id: str) -> ResearchLoopState:
        state = self.require_state(session_id)
        state.status = ResearchLoopStatus.STOPPED
        state.last_action = LoopControlAction.STOP.value
        if not state.partial_answer and state.metadata.get("final_answer"):
            state.partial_answer = _truncate_partial(state.metadata.get("final_answer"))
        state.updated_at = _now()
        self._sync_plan_progress(state)
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
        self._sync_plan_progress(state)
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

