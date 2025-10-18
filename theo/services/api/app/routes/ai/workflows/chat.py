"""Chat workflow routes and supporting helpers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Sequence, TypeAlias
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from theo.services.api.app.ai import run_guarded_chat
from theo.services.api.app.ai.audit_logging import (
    AuditLogWriter,
    compute_prompt_hash,
    serialise_citations,
)
from theo.services.api.app.ai import memory_index as memory_index_module
from theo.services.api.app.ai.rag import GuardrailError, RAGAnswer, ensure_completion_safe
from theo.services.api.app.ai.trails import TrailService
from theo.services.api.app.ai.memory_metadata import (
    MemoryFocus,
    extract_memory_metadata,
)
from theo.application.facades.database import get_session
from theo.application.facades.settings import get_settings
from theo.services.api.app.persistence_models import ChatSession
from theo.services.api.app.intent.tagger import get_intent_tagger
from theo.services.api.app.models.ai import (
    ChatGoalProgress,
    ChatGoalState,
    ChatMemoryEntry,
    ChatSessionMessage,
    ChatSessionPreferences,
    ChatSessionRequest,
    ChatSessionResponse,
    ChatSessionState,
    CHAT_SESSION_MEMORY_CHAR_BUDGET,
    CHAT_SESSION_TOTAL_CHAR_BUDGET,
    GoalCloseRequest,
    GoalPriorityUpdateRequest,
    IntentTagPayload,
)
from .guardrails import extract_refusal_text, guardrail_http_exception
from .utils import has_filters

from ....errors import AIWorkflowError, Severity

if TYPE_CHECKING:  # pragma: no cover - runtime import for FastAPI annotations
    from fastapi.responses import JSONResponse

    ChatTurnReturn: TypeAlias = ChatSessionResponse | JSONResponse
else:  # pragma: no cover - hinting only
    ChatTurnReturn: TypeAlias = ChatSessionResponse

router = APIRouter()

LOGGER = logging.getLogger(__name__)

# Note: HTTP_413_REQUEST_ENTITY_TOO_LARGE is deprecated but HTTP_413_CONTENT_TOO_LARGE
# doesn't exist in starlette yet. Use the old constant directly to avoid deprecation noise.
_PAYLOAD_TOO_LARGE_STATUS = 413

_MAX_STORED_MEMORY = 10
_MAX_CONTEXT_SNIPPETS = 4
_MEMORY_TEXT_LIMIT = 600
_MEMORY_SUMMARY_LIMIT = 400
_BAD_REQUEST_RESPONSE = {status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"}}
_NOT_FOUND_RESPONSE = {status.HTTP_404_NOT_FOUND: {"description": "Resource not found"}}
CHAT_PLAN = "\n".join(
    [
        "- Retrieve supporting passages using hybrid search",
        "- Compose a grounded assistant reply with citations",
        "- Validate guardrails before finalising the turn",
    ]
)

_GOAL_DECLARE_PATTERNS = [
    re.compile(r"^\s*goal\s*[:\-]\s*(?P<title>.+)$", re.IGNORECASE),
    re.compile(r"^\s*objective\s*[:\-]\s*(?P<title>.+)$", re.IGNORECASE),
    re.compile(r"^\s*my\s+goal\s+is\s+(?P<title>.+)$", re.IGNORECASE),
]
_GOAL_RESUME_PATTERN = re.compile(
    r"^\s*resume\s+(?:goal|objective)\s*(?::|\s)\s*(?P<identifier>.+)$",
    re.IGNORECASE,
)


@dataclass
class GoalDirective:
    action: str
    goal: ChatGoalState | None = None
    title: str | None = None
    identifier: str | None = None


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value.strip()
    truncated = value[: max(limit - 1, 0)].rstrip()
    return f"{truncated}…" if truncated else value[:limit]


def _load_goal_entries(record: ChatSession | None) -> list[ChatGoalState]:
    goals: list[ChatGoalState] = []
    if record is None:
        return goals
    raw_goals = getattr(record, "goals", []) or []
    for raw in raw_goals:
        try:
            goal = ChatGoalState.model_validate(raw)
        except Exception:
            LOGGER.debug(
                "Skipping invalid chat goal payload for session %s",
                record.id,
                exc_info=True,
            )
            continue
        goals.append(goal)
    _normalise_goal_priorities(goals)
    return goals


def _dump_goal_entries(goals: Sequence[ChatGoalState]) -> list[dict[str, object]]:
    return [goal.model_dump(mode="json", exclude_none=True) for goal in goals]


def _normalise_goal_priorities(goals: list[ChatGoalState]) -> None:
    active: list[ChatGoalState] = [goal for goal in goals if goal.status == "active"]
    inactive: list[ChatGoalState] = [goal for goal in goals if goal.status != "active"]
    active.sort(key=lambda goal: (goal.priority, goal.created_at))
    inactive.sort(key=lambda goal: (goal.priority, goal.created_at))
    for index, goal in enumerate(active):
        goal.priority = index
    offset = len(active)
    for index, goal in enumerate(inactive, start=offset):
        goal.priority = index
    goals[:] = active + inactive


def _select_primary_goal(goals: Sequence[ChatGoalState]) -> ChatGoalState | None:
    active = [goal for goal in goals if goal.status == "active"]
    if not active:
        return None
    active.sort(key=lambda goal: goal.last_interaction_at, reverse=True)
    active.sort(key=lambda goal: goal.priority)
    return active[0]


def _find_goal_by_identifier(
    identifier: str, goals: Sequence[ChatGoalState]
) -> ChatGoalState | None:
    normalised = identifier.strip().lower()
    for goal in goals:
        if goal.id.lower() == normalised:
            return goal
    for goal in goals:
        if goal.title.strip().lower() == normalised:
            return goal
    return None


def _resolve_goal_directive(
    message: str, goals: Sequence[ChatGoalState]
) -> GoalDirective:
    cleaned = message.strip()
    if cleaned:
        for pattern in _GOAL_DECLARE_PATTERNS:
            match = pattern.match(cleaned)
            if match:
                title = match.group("title").strip()
                return GoalDirective(action="declare", title=title)
        resume = _GOAL_RESUME_PATTERN.match(cleaned)
        if resume:
            identifier = resume.group("identifier").strip()
            goal = _find_goal_by_identifier(identifier, goals)
            if goal is not None:
                return GoalDirective(
                    action="resume", goal=goal, identifier=identifier
                )
            return GoalDirective(action="declare", title=identifier)
    return GoalDirective(action="none", goal=_select_primary_goal(goals))


def _reprioritise_goal(
    goals: list[ChatGoalState], goal: ChatGoalState, desired_index: int
) -> None:
    desired_index = max(0, desired_index)
    active = [item for item in goals if item.status == "active" and item.id != goal.id]
    active.sort(key=lambda g: g.priority)
    insert_at = min(desired_index, len(active))
    active.insert(insert_at, goal)
    for index, item in enumerate(active):
        item.priority = index
    inactive = [item for item in goals if item.status != "active"]
    inactive.sort(key=lambda g: (g.priority, g.created_at))
    offset = len(active)
    for index, item in enumerate(inactive, start=offset):
        item.priority = index
    goals[:] = active + inactive


def _touch_goal(goal: ChatGoalState, summary: str | None, now: datetime) -> None:
    goal.summary = summary
    goal.last_interaction_at = now
    goal.updated_at = now


def _resolve_preferences(payload: ChatSessionRequest) -> ChatSessionPreferences:
    if payload.preferences:
        return payload.preferences
    default_filters = payload.filters if has_filters(payload.filters) else None
    return ChatSessionPreferences(
        mode=payload.stance or payload.mode_id or payload.model,
        default_filters=default_filters,
        frequently_opened_panels=[],
    )


def _load_memory_entries(record: ChatSession | None) -> list[ChatMemoryEntry]:
    entries: list[ChatMemoryEntry] = []
    if not record:
        return entries
    raw_entries = record.memory_snippets or []
    for raw in raw_entries:
        try:
            entry = ChatMemoryEntry.model_validate(raw)
        except Exception:
            LOGGER.debug(
                "Skipping invalid chat memory snippet for session %s", record.id, exc_info=True
            )
            continue
        entries.append(entry)
    entries.sort(key=lambda entry: entry.created_at)
    return entries


def _prepare_memory_context(
    entries: Sequence[ChatMemoryEntry],
    *,
    query: str | None = None,
    focus: MemoryFocus | None = None,
) -> list[str]:
    if not entries:
        return []

    ranked_entries: list[ChatMemoryEntry] = []
    seen_ids: set[int] = set()

    if query:
        memory_index = memory_index_module.get_memory_index()
        try:
            query_embedding = memory_index.embed_query(query)
        except Exception:  # pragma: no cover - defensive guardrail
            LOGGER.debug("Failed to embed chat query for memory ranking", exc_info=True)
            query_embedding = None
        else:
            if query_embedding:
                scored: list[tuple[float, ChatMemoryEntry]] = []
                for entry in entries:
                    if not entry.embedding:
                        continue
                    score = memory_index.score_similarity(
                        query_embedding, entry.embedding
                    )
                    if score is None:
                        continue
                    scored.append((score, entry))
                scored.sort(key=lambda item: item[0], reverse=True)
                for _, entry in scored:
                    if len(ranked_entries) >= _MAX_CONTEXT_SNIPPETS:
                        break
                    entry_id = id(entry)
                    if entry_id in seen_ids:
                        continue
                    ranked_entries.append(entry)
                    seen_ids.add(entry_id)

    ordered = sorted(entries, key=lambda entry: entry.created_at, reverse=True)
    if focus:
        matched: list[ChatMemoryEntry] = []
        remainder: list[ChatMemoryEntry] = []
        for entry in ordered:
            if focus.matches(entry):
                matched.append(entry)
            else:
                remainder.append(entry)
        candidates = matched + remainder
    else:
        candidates = ordered

    for entry in candidates:
        if len(ranked_entries) >= _MAX_CONTEXT_SNIPPETS:
            break
        entry_id = id(entry)
        if entry_id in seen_ids:
            continue
        ranked_entries.append(entry)
        seen_ids.add(entry_id)

    remaining = CHAT_SESSION_MEMORY_CHAR_BUDGET
    selected: list[tuple[ChatMemoryEntry, str]] = []
    for entry in ranked_entries:
        base = memory_index_module.render_memory_snippet(
            entry.question,
            entry.answer,
            answer_summary=entry.answer_summary,
        )
        extras: list[str] = []
        key_entities = getattr(entry, "key_entities", None) or []
        if key_entities:
            extras.append(f"Key: {', '.join(key_entities[:3])}")
        recommended_actions = getattr(entry, "recommended_actions", None) or []
        if recommended_actions:
            extras.append(f"Next: {recommended_actions[0]}")
        snippet = base if not extras else f"{base} | {' | '.join(extras)}"
        snippet = _truncate_text(snippet, min(_MEMORY_TEXT_LIMIT * 2, remaining))
        if not snippet:
            continue
        if len(snippet) > remaining and selected:
            break
        snippet = snippet[:remaining]
        selected.append((entry, snippet))
        remaining -= len(snippet)
        if remaining <= 0 or len(selected) >= _MAX_CONTEXT_SNIPPETS:
            break

    if not selected:
        return []

    if focus:
        matched_pairs = [pair for pair in selected if focus.matches(pair[0])]
        remainder_pairs = [pair for pair in selected if not focus.matches(pair[0])]
        matched_pairs.sort(key=lambda pair: pair[0].created_at, reverse=True)
        remainder_pairs.sort(key=lambda pair: pair[0].created_at, reverse=True)
        ordered_pairs = matched_pairs + remainder_pairs
    else:
        ordered_pairs = selected

    return [snippet for _, snippet in ordered_pairs]


def _collect_document_ids(answer: RAGAnswer) -> list[str]:
    doc_ids: list[str] = []
    for citation in answer.citations or []:
        document_id = getattr(citation, "document_id", None)
        if document_id and document_id not in doc_ids:
            doc_ids.append(document_id)
    return doc_ids


def _persist_chat_session(
    session: Session,
    *,
    existing: ChatSession | None,
    session_id: str,
    user_id: str | None,
    stance: str | None,
    question: str,
    prompt: str | None,
    intent_tags: Sequence[IntentTagPayload] | None,
    message: ChatSessionMessage,
    answer: RAGAnswer,
    preferences: ChatSessionPreferences,
    goals: list[ChatGoalState],
    active_goal: ChatGoalState | None,
    memory_entry: ChatMemoryEntry | None = None,
) -> ChatSession:
    now = datetime.now(UTC)
    entries = _load_memory_entries(existing)
    normalized_intent_tags: list[IntentTagPayload] | None = None
    if intent_tags:
        normalized_intent_tags = [
            tag if isinstance(tag, IntentTagPayload) else IntentTagPayload.model_validate(tag)
            for tag in intent_tags
        ]
    metadata = extract_memory_metadata(
        question=question,
        answer=answer,
        intent_tags=normalized_intent_tags,
    )

    if memory_entry is None:
        new_entry = ChatMemoryEntry(
            question=_truncate_text(question, _MEMORY_TEXT_LIMIT),
            answer=_truncate_text(message.content, _MEMORY_TEXT_LIMIT),
            prompt=_truncate_text(prompt, _MEMORY_TEXT_LIMIT) if prompt else None,
            intent_tags=normalized_intent_tags,
            answer_summary=(
                _truncate_text(answer.summary, _MEMORY_SUMMARY_LIMIT)
                if answer.summary
                else None
            ),
            citations=list(answer.citations or []),
            document_ids=_collect_document_ids(answer),
            topics=metadata.topics,
            entities=metadata.entities,
            goal_ids=metadata.goal_ids,
            source_types=metadata.source_types,
            sentiment=metadata.sentiment,
            created_at=now,
        )
    else:
        new_entry = memory_entry
        new_entry.question = _truncate_text(new_entry.question, _MEMORY_TEXT_LIMIT)
        new_entry.answer = _truncate_text(new_entry.answer, _MEMORY_TEXT_LIMIT)
        new_entry.prompt = (
            _truncate_text(new_entry.prompt, _MEMORY_TEXT_LIMIT)
            if new_entry.prompt
            else None
        )
        new_entry.intent_tags = normalized_intent_tags
        if new_entry.answer_summary:
            new_entry.answer_summary = _truncate_text(
                new_entry.answer_summary, _MEMORY_SUMMARY_LIMIT
            )
        elif answer.summary:
            new_entry.answer_summary = _truncate_text(
                answer.summary, _MEMORY_SUMMARY_LIMIT
            )
        if not new_entry.citations:
            new_entry.citations = list(answer.citations or [])
        if not new_entry.document_ids:
            new_entry.document_ids = _collect_document_ids(answer)
        if not new_entry.topics:
            new_entry.topics = metadata.topics
        if not new_entry.entities:
            new_entry.entities = metadata.entities
        if not new_entry.goal_ids:
            new_entry.goal_ids = metadata.goal_ids
        if not new_entry.source_types:
            new_entry.source_types = metadata.source_types
        if new_entry.sentiment is None:
            new_entry.sentiment = metadata.sentiment
        if new_entry.created_at is None:
            new_entry.created_at = now

    if active_goal is not None:
        if new_entry.goal_id is None:
            new_entry.goal_id = active_goal.id
        if new_entry.trail_id is None:
            new_entry.trail_id = active_goal.trail_id
    try:
        memory_index = memory_index_module.get_memory_index()
        if memory_entry is None or new_entry.embedding is None:
            embedding = memory_index.embed_entry(new_entry)
        else:
            embedding = None
        if embedding:
            new_entry.embedding = embedding
            new_entry.embedding_model = memory_index.model_name
    except Exception:  # pragma: no cover - defensive guard
        LOGGER.debug(
            "Unable to persist chat memory embedding for session %s", session_id,
            exc_info=True,
        )
    entries.append(new_entry)
    if len(entries) > _MAX_STORED_MEMORY:
        entries = entries[-_MAX_STORED_MEMORY:]
    raw_entries = [entry.model_dump(mode="json") for entry in entries]
    aggregated_docs: list[str] = []
    for entry in entries:
        for doc_id in entry.document_ids:
            if doc_id not in aggregated_docs:
                aggregated_docs.append(doc_id)

    pref_dict = preferences.model_dump(mode="json") if preferences else None

    updated_goals = list(goals)
    if active_goal is not None:
        summary_text = new_entry.answer_summary or new_entry.answer
        _touch_goal(active_goal, summary_text, now)
        replaced = False
        for index, goal in enumerate(updated_goals):
            if goal.id == active_goal.id:
                updated_goals[index] = active_goal
                replaced = True
                break
        if not replaced:
            updated_goals.append(active_goal)
    _normalise_goal_priorities(updated_goals)
    goals.clear()
    goals.extend(updated_goals)
    raw_goals = _dump_goal_entries(updated_goals)

    if existing is None:
        record = ChatSession(
            id=session_id,
            user_id=user_id,
            stance=stance,
            summary=new_entry.answer_summary or new_entry.answer,
            memory_snippets=raw_entries,
            document_ids=aggregated_docs,
            goals=raw_goals,
            preferences=pref_dict,
            created_at=now,
            updated_at=now,
            last_interaction_at=now,
        )
    else:
        record = existing
        if user_id:
            record.user_id = user_id
        record.stance = stance or record.stance
        record.summary = new_entry.answer_summary or new_entry.answer
        record.memory_snippets = raw_entries
        record.document_ids = aggregated_docs
        record.goals = raw_goals
        record.preferences = pref_dict
        record.updated_at = now
        record.last_interaction_at = now

    session.add(record)
    session.flush()
    return record


def _serialise_chat_session(record: ChatSession) -> ChatSessionState:
    entries = _load_memory_entries(record)
    goals = _load_goal_entries(record)
    preferences: ChatSessionPreferences | None = None
    if record.preferences:
        try:
            preferences = ChatSessionPreferences.model_validate(record.preferences)
        except Exception:
            LOGGER.debug(
                "Unable to parse chat session preferences for %s", record.id, exc_info=True
            )
            preferences = None
    document_ids = list(record.document_ids or [])
    return ChatSessionState(
        session_id=record.id,
        stance=record.stance,
        summary=record.summary,
        document_ids=document_ids,
        preferences=preferences,
        memory=entries,
        goals=goals,
        created_at=record.created_at,
        updated_at=record.updated_at,
        last_interaction_at=record.last_interaction_at,
    )


@router.post(
    "/chat",
    response_model=ChatSessionResponse,
    response_model_exclude_none=True,
    responses=_BAD_REQUEST_RESPONSE,
)
def chat_turn(
    payload: ChatSessionRequest, session: Session = Depends(get_session)
) -> ChatTurnReturn:
    if not payload.messages:
        raise AIWorkflowError(
            "messages cannot be empty",
            code="AI_CHAT_EMPTY_MESSAGES",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    total_message_chars = sum(len(message.content) for message in payload.messages)
    if total_message_chars > CHAT_SESSION_TOTAL_CHAR_BUDGET:
        raise AIWorkflowError(
            "chat payload exceeds size limit",
            code="AI_CHAT_PAYLOAD_TOO_LARGE",
            status_code=_PAYLOAD_TOO_LARGE_STATUS,
        )
    last_user = next(
        (message for message in reversed(payload.messages) if message.role == "user"),
        None,
    )
    if last_user is None:
        raise AIWorkflowError(
            "missing user message",
            code="AI_CHAT_MISSING_USER_MESSAGE",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    question = last_user.content.strip()
    if not question:
        raise AIWorkflowError(
            "user message cannot be blank",
            code="AI_CHAT_EMPTY_USER_MESSAGE",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    settings = get_settings()
    intent_tags: list[IntentTagPayload] | None = None
    serialized_intent_tags: list[dict[str, object]] | None = None
    if settings.intent_tagger_enabled:
        try:
            tagger = get_intent_tagger(settings)
            if tagger is not None:
                predicted = tagger.predict(question)
                tag_payload = IntentTagPayload(**predicted.to_payload())
                intent_tags = [tag_payload]
                serialized_intent_tags = [
                    tag_payload.model_dump(exclude_none=True)
                ]
        except Exception:  # noqa: BLE001 - tagging failures should not block chat flow
            LOGGER.warning(
                "Intent tagging failed for chat request", exc_info=True
            )

    session_id = payload.session_id or str(uuid4())
    trail_service = TrailService(session)
    audit_logger = AuditLogWriter.from_session(session)

    message: ChatSessionMessage | None = None
    answer: RAGAnswer | None = None

    existing_session = session.get(ChatSession, session_id)
    preferences = _resolve_preferences(payload)
    memory_entries = _load_memory_entries(existing_session)
    memory_context = _prepare_memory_context(memory_entries)
    goals = _load_goal_entries(existing_session)
    directive = _resolve_goal_directive(question, goals)
    active_goal = directive.goal
    recorder_user_id = (
        payload.recorder_metadata.user_id if payload.recorder_metadata else None
    )
    focus_metadata = extract_memory_metadata(
        question=question,
        answer=None,
        intent_tags=intent_tags,
    )
    memory_focus = focus_metadata.to_focus()
    memory_context = _prepare_memory_context(
        memory_entries, query=question, focus=memory_focus
    )

    if memory_context:
        budget_remaining = CHAT_SESSION_TOTAL_CHAR_BUDGET - total_message_chars
        if budget_remaining <= 0:
            memory_context = []
        else:
            trimmed: list[str] = []
            remaining_budget = budget_remaining
            for snippet in reversed(memory_context):
                if remaining_budget <= 0:
                    break
                adjusted = snippet
                if len(adjusted) > remaining_budget:
                    adjusted = _truncate_text(adjusted, remaining_budget)
                if not adjusted:
                    continue
                trimmed.append(adjusted)
                remaining_budget -= len(adjusted)
            memory_context = list(reversed(trimmed)) if trimmed else []

    log_inputs: dict[str, object] = {
        "messages": [message.model_dump(mode="json") for message in payload.messages],
        "filters": payload.filters.model_dump(exclude_none=True),
    }
    if payload.osis is not None:
        log_inputs["osis"] = payload.osis
    if payload.prompt is not None:
        log_inputs["prompt"] = payload.prompt
    if payload.model is not None:
        log_inputs["model"] = payload.model
    if payload.mode_id is not None:
        log_inputs["mode_id"] = payload.mode_id
    if payload.stance is not None:
        log_inputs["stance"] = payload.stance
    if payload.session_id is not None:
        log_inputs["session_id"] = payload.session_id
    if payload.recorder_metadata is not None:
        log_inputs["recorder_metadata"] = payload.recorder_metadata.model_dump(
            mode="json", exclude_none=True
        )
    prompt_hash = compute_prompt_hash(question, log_inputs)

    try:
        recorder_context = None
        if directive.action == "declare":
            goal_title = directive.title or question
            recorder_context = trail_service.start_trail(
                workflow="chat_goal",
                plan_md=_truncate_text(goal_title, _MEMORY_SUMMARY_LIMIT),
                mode="chat_goal",
                input_payload={
                    "session_id": session_id,
                    "goal_title": goal_title,
                    "request": payload.model_dump(mode="json"),
                },
                user_id=recorder_user_id,
            )
            goal_timestamp = datetime.now(UTC)
            active_goal = ChatGoalState(
                id=str(uuid4()),
                title=_truncate_text(goal_title, _MEMORY_TEXT_LIMIT),
                trail_id=recorder_context.trail.id,
                status="active",
                priority=0,
                summary=None,
                created_at=goal_timestamp,
                updated_at=goal_timestamp,
                last_interaction_at=goal_timestamp,
            )
            goals.append(active_goal)
            _reprioritise_goal(goals, active_goal, 0)
        elif directive.action == "resume" and active_goal is not None:
            recorder_context = trail_service.resume_trail(active_goal.trail_id)
            _reprioritise_goal(goals, active_goal, 0)
        elif directive.action == "resume":
            goal_title = directive.title or question
            recorder_context = trail_service.start_trail(
                workflow="chat_goal",
                plan_md=_truncate_text(goal_title, _MEMORY_SUMMARY_LIMIT),
                mode="chat_goal",
                input_payload={
                    "session_id": session_id,
                    "goal_title": goal_title,
                    "request": payload.model_dump(mode="json"),
                },
                user_id=recorder_user_id,
            )
            goal_timestamp = datetime.now(UTC)
            active_goal = ChatGoalState(
                id=str(uuid4()),
                title=_truncate_text(goal_title, _MEMORY_TEXT_LIMIT),
                trail_id=recorder_context.trail.id,
                status="active",
                priority=0,
                summary=None,
                created_at=goal_timestamp,
                updated_at=goal_timestamp,
                last_interaction_at=goal_timestamp,
            )
            goals.append(active_goal)
            _reprioritise_goal(goals, active_goal, 0)
        elif active_goal is not None:
            recorder_context = trail_service.resume_trail(active_goal.trail_id)
        else:
            recorder_context = trail_service.start_trail(
                workflow="chat",
                plan_md=CHAT_PLAN,
                mode=payload.mode_id or payload.stance or "chat",
                input_payload=payload.model_dump(mode="json"),
                user_id=recorder_user_id,
            )

        active_reasoning_mode = payload.mode_id or payload.stance

        with recorder_context as recorder:
            if active_reasoning_mode:
                recorder.trail.mode = active_reasoning_mode
            answer = run_guarded_chat(
                session,
                question=question,
                osis=payload.osis,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
                memory_context=memory_context,
                mode=active_reasoning_mode,
            )
            ensure_completion_safe(answer.model_output or answer.summary)

            message_text = extract_refusal_text(answer)
            message = ChatSessionMessage(role="assistant", content=message_text)
            audit_logger.log(
                workflow="chat",
                prompt_hash=prompt_hash,
                model_preset=(
                    answer.model_name
                    or payload.model
                    or payload.mode_id
                    or payload.stance
                ),
                inputs=log_inputs,
                outputs={
                    "message": message.model_dump(mode="json"),
                    "answer": answer.model_dump(mode="json"),
                },
                citations=serialise_citations(answer.citations),
                status="generated",
            )
            _persist_chat_session(
                session,
                existing=existing_session,
                session_id=session_id,
                user_id=recorder_user_id,
                stance=active_reasoning_mode or payload.model,
                question=question,
                prompt=payload.prompt,
                intent_tags=intent_tags,
                message=message,
                answer=answer,
                preferences=preferences,
                goals=goals,
                active_goal=active_goal,
            )
            trail_output = {
                "session_id": session_id,
                "answer": answer,
                "message": message,
            }
            if active_goal is not None:
                trail_output["goal_id"] = active_goal.id
                trail_output["trail_id"] = active_goal.trail_id
            if serialized_intent_tags:
                trail_output["intent_tags"] = serialized_intent_tags
            recorder.finalize(
                final_md=answer.summary,
                output_payload=trail_output,
                status="running" if active_goal is not None else "completed",
            )
    except GuardrailError as exc:
        response = guardrail_http_exception(
            exc,
            session=session,
            question=question,
            osis=payload.osis,
            filters=payload.filters,
        )
        response_payload: dict[str, object] | None = None
        try:
            body = getattr(response, "body", b"")
            if body:
                response_payload = json.loads(body.decode("utf-8"))
        except Exception:  # noqa: BLE001 - best effort logging
            LOGGER.debug("Unable to decode guardrail response for audit logging", exc_info=True)
            response_payload = None
        citations_payload: list[dict[str, object]] | None = None
        outputs_payload: dict[str, object] | None = None
        if isinstance(response_payload, dict):
            answer_payload = response_payload.get("answer")
            if isinstance(answer_payload, dict):
                raw_citations = answer_payload.get("citations")
                if isinstance(raw_citations, list):
                    citations_payload = [
                        citation
                        for citation in raw_citations
                        if isinstance(citation, dict)
                    ]
            outputs_payload = {
                key: value
                for key, value in response_payload.items()
                if key in {"detail", "message", "answer", "guardrail_advisory"}
            }
        audit_logger.log(
            workflow="chat",
            prompt_hash=prompt_hash,
            model_preset=payload.model,
            inputs=log_inputs,
            outputs=outputs_payload or {"error": str(exc)},
            citations=citations_payload,
            status="refused",
        )
        return response

    if message is None or answer is None:
        raise AIWorkflowError(
            "failed to compose chat response",
            code="AI_CHAT_COMPOSITION_FAILED",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=Severity.CRITICAL,
        )

    return ChatSessionResponse(
        session_id=session_id,
        message=message,
        answer=answer,
        intent_tags=intent_tags,
    )


@router.get(
    "/chat/{session_id}",
    response_model=ChatSessionState,
    response_model_exclude_none=True,
    responses=_NOT_FOUND_RESPONSE,
)
def get_chat_session(session_id: str, session: Session = Depends(get_session)) -> ChatSessionState:
    record = session.get(ChatSession, session_id)
    if record is None:
        raise AIWorkflowError(
            "chat session not found",
            code="AI_CHAT_SESSION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return _serialise_chat_session(record)


@router.get(
    "/chat/{session_id}/goals",
    response_model=ChatGoalProgress,
    response_model_exclude_none=True,
    responses=_NOT_FOUND_RESPONSE,
)
def list_chat_goals(
    session_id: str, session: Session = Depends(get_session)
) -> ChatGoalProgress:
    record = session.get(ChatSession, session_id)
    if record is None:
        raise AIWorkflowError(
            "chat session not found",
            code="AI_CHAT_SESSION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    goals = _load_goal_entries(record)
    return ChatGoalProgress(goals=goals)


@router.post(
    "/chat/{session_id}/goals/{goal_id}/close",
    response_model=ChatGoalState,
    response_model_exclude_none=True,
    responses=_NOT_FOUND_RESPONSE,
)
def close_chat_goal(
    session_id: str,
    goal_id: str,
    payload: GoalCloseRequest | None = None,
    session: Session = Depends(get_session),
) -> ChatGoalState:
    record = session.get(ChatSession, session_id)
    if record is None:
        raise AIWorkflowError(
            "chat session not found",
            code="AI_CHAT_SESSION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    goals = _load_goal_entries(record)
    goal = next((item for item in goals if item.id == goal_id), None)
    if goal is None:
        raise AIWorkflowError(
            "goal not found",
            code="AI_CHAT_GOAL_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if goal.status != "closed":
        now = datetime.now(UTC)
        goal.status = "closed"
        goal.updated_at = now
        goal.last_interaction_at = now
        if payload and payload.summary:
            goal.summary = payload.summary
        _normalise_goal_priorities(goals)
        record.goals = _dump_goal_entries(goals)
        session.add(record)
        trail_service = TrailService(session)
        trail = trail_service.get_trail(goal.trail_id)
        if trail is not None:
            trail.status = "completed"
            if payload and payload.summary:
                trail.final_md = payload.summary
            trail.completed_at = now
            trail.updated_at = now
            session.add(trail)
        session.commit()
    return goal


@router.post(
    "/chat/{session_id}/goals/{goal_id}/priority",
    response_model=ChatGoalProgress,
    response_model_exclude_none=True,
    responses=_NOT_FOUND_RESPONSE,
)
def update_goal_priority(
    session_id: str,
    goal_id: str,
    payload: GoalPriorityUpdateRequest,
    session: Session = Depends(get_session),
) -> ChatGoalProgress:
    record = session.get(ChatSession, session_id)
    if record is None:
        raise AIWorkflowError(
            "chat session not found",
            code="AI_CHAT_SESSION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    goals = _load_goal_entries(record)
    goal = next((item for item in goals if item.id == goal_id), None)
    if goal is None:
        raise AIWorkflowError(
            "goal not found",
            code="AI_CHAT_GOAL_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    _reprioritise_goal(goals, goal, payload.priority)
    goal.updated_at = datetime.now(UTC)
    record.goals = _dump_goal_entries(goals)
    session.add(record)
    session.commit()
    return ChatGoalProgress(goals=goals)


__all__ = [
    "router",
    "chat_turn",
    "get_chat_session",
    "list_chat_goals",
    "close_chat_goal",
    "update_goal_priority",
    "_prepare_memory_context",
    "_load_memory_entries",
]
