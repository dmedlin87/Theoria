"""Chat workflow routes and supporting helpers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Sequence
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from theo.services.api.app.ai import run_guarded_chat
from theo.services.api.app.ai.rag import GuardrailError, RAGAnswer, ensure_completion_safe
from theo.services.api.app.ai.trails import TrailService
from theo.services.api.app.core.database import get_session
from theo.services.api.app.core.settings import get_settings
from theo.services.api.app.db.models import ChatSession
from theo.services.api.app.intent.tagger import get_intent_tagger
from theo.services.api.app.models.ai import (
    ChatMemoryEntry,
    ChatSessionMessage,
    ChatSessionPreferences,
    ChatSessionRequest,
    ChatSessionResponse,
    ChatSessionState,
    CHAT_SESSION_MEMORY_CHAR_BUDGET,
    CHAT_SESSION_TOTAL_CHAR_BUDGET,
    IntentTagPayload,
)
from .guardrails import extract_refusal_text, guardrail_http_exception
from .utils import has_filters

router = APIRouter()

LOGGER = logging.getLogger(__name__)

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


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value.strip()
    truncated = value[: max(limit - 1, 0)].rstrip()
    return f"{truncated}…" if truncated else value[:limit]


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


def _prepare_memory_context(entries: Sequence[ChatMemoryEntry]) -> list[str]:
    if not entries:
        return []
    remaining = CHAT_SESSION_MEMORY_CHAR_BUDGET
    selected: list[str] = []
    for entry in reversed(entries):
        answer_text = (entry.answer_summary or entry.answer or "").strip()
        question_text = entry.question.strip()
        snippet = _truncate_text(
            f"Q: {question_text} | A: {answer_text}",
            min(_MEMORY_TEXT_LIMIT * 2, remaining),
        )
        if not snippet:
            continue
        if len(snippet) > remaining and selected:
            break
        snippet = snippet[:remaining]
        selected.append(snippet)
        remaining -= len(snippet)
        if remaining <= 0 or len(selected) >= _MAX_CONTEXT_SNIPPETS:
            break
    return list(reversed(selected))


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
    message: ChatSessionMessage,
    answer: RAGAnswer,
    preferences: ChatSessionPreferences,
) -> ChatSession:
    now = datetime.now(UTC)
    entries = _load_memory_entries(existing)
    new_entry = ChatMemoryEntry(
        question=_truncate_text(question, _MEMORY_TEXT_LIMIT),
        answer=_truncate_text(message.content, _MEMORY_TEXT_LIMIT),
        prompt=_truncate_text(prompt, _MEMORY_TEXT_LIMIT) if prompt else None,
        answer_summary=(
            _truncate_text(answer.summary, _MEMORY_SUMMARY_LIMIT)
            if answer.summary
            else None
        ),
        citations=list(answer.citations or []),
        document_ids=_collect_document_ids(answer),
        created_at=now,
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

    if existing is None:
        record = ChatSession(
            id=session_id,
            user_id=user_id,
            stance=stance,
            summary=new_entry.answer_summary or new_entry.answer,
            memory_snippets=raw_entries,
            document_ids=aggregated_docs,
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
        record.preferences = pref_dict
        record.updated_at = now
        record.last_interaction_at = now

    session.add(record)
    session.flush()
    return record


def _serialise_chat_session(record: ChatSession) -> ChatSessionState:
    entries = _load_memory_entries(record)
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
) -> ChatSessionResponse:
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    total_message_chars = sum(len(message.content) for message in payload.messages)
    if total_message_chars > CHAT_SESSION_TOTAL_CHAR_BUDGET:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="chat payload exceeds size limit",
        )
    last_user = next(
        (message for message in reversed(payload.messages) if message.role == "user"),
        None,
    )
    if last_user is None:
        raise HTTPException(status_code=400, detail="missing user message")
    question = last_user.content.strip()
    if not question:
        raise HTTPException(status_code=400, detail="user message cannot be blank")

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

    message: ChatSessionMessage | None = None
    answer: RAGAnswer | None = None

    existing_session = session.get(ChatSession, session_id)
    preferences = _resolve_preferences(payload)
    memory_entries = _load_memory_entries(existing_session)
    memory_context = _prepare_memory_context(memory_entries)

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

    try:
        with trail_service.start_trail(
            workflow="chat",
            plan_md=CHAT_PLAN,
            mode="chat",
            input_payload=payload.model_dump(mode="json"),
            user_id=(
                payload.recorder_metadata.user_id
                if payload.recorder_metadata
                else None
            ),
        ) as recorder:
            answer = run_guarded_chat(
                session,
                question=question,
                osis=payload.osis,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
                memory_context=memory_context,
            )
            ensure_completion_safe(answer.model_output or answer.summary)

            message_text = extract_refusal_text(answer)
            message = ChatSessionMessage(role="assistant", content=message_text)
            _persist_chat_session(
                session,
                existing=existing_session,
                session_id=session_id,
                user_id=(
                    payload.recorder_metadata.user_id
                    if payload.recorder_metadata
                    else None
                ),
                stance=payload.stance or payload.mode_id,
                question=question,
                prompt=payload.prompt,
                message=message,
                answer=answer,
                preferences=preferences,
            )
            trail_output = {
                "session_id": session_id,
                "answer": answer,
                "message": message,
            }
            if serialized_intent_tags:
                trail_output["intent_tags"] = serialized_intent_tags
            recorder.finalize(
                final_md=answer.summary,
                output_payload=trail_output,
            )
    except GuardrailError as exc:
        return guardrail_http_exception(
            exc,
            session=session,
            question=question,
            osis=payload.osis,
            filters=payload.filters,
        )

    if message is None or answer is None:
        raise HTTPException(status_code=500, detail="failed to compose chat response")

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
        raise HTTPException(status_code=404, detail="chat session not found")
    return _serialise_chat_session(record)


__all__ = [
    "router",
    "chat_turn",
    "get_chat_session",
    "_prepare_memory_context",
    "_load_memory_entries",
]
