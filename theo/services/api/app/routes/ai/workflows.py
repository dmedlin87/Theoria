"""Routes exposing AI-assisted workflows."""

from __future__ import annotations

from collections import defaultdict
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping, Sequence
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...ai import (
    build_guardrail_refusal,
    build_sermon_deliverable,
    build_transcript_deliverable,
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
    generate_verse_brief,
    run_corpus_curation,
    run_guarded_chat,
    run_research_reconciliation,
)
from ...ai.passage import PassageResolutionError, resolve_passage_reference
from ...ai.rag import (
    GuardrailError,
    RAGAnswer,
    RAGCitation,
    REFUSAL_MODEL_NAME,
    ensure_completion_safe,
)
from ...ai.registry import LLMModel, LLMRegistry, save_llm_registry
from ...ai.trails import TrailService
from ...core.database import get_session
from ...core.settings import get_settings
from ...core.settings_store import load_setting, save_setting
from ...db.models import ChatSession, Document, Passage
from ...export.formatters import build_document_export
from ...models.ai import (
    AIFeaturesResponse,
    ChatMemoryEntry,
    ChatSessionMessage,
    ChatSessionPreferences,
    ChatSessionRequest,
    ChatSessionResponse,
    ChatSessionState,
    CHAT_SESSION_MEMORY_CHAR_BUDGET,
    CHAT_SESSION_TOTAL_CHAR_BUDGET,
    CitationExportRequest,
    CitationExportResponse,
    CollaborationRequest,
    ComparativeAnalysisRequest,
    CorpusCurationRequest,
    DevotionalRequest,
    ExportDeliverableResponse,
    ExportPresetId,
    GuardrailAdvisory,
    GuardrailFailureMetadata,
    GuardrailSuggestion,
    IntentTagPayload,
    LLMDefaultRequest,
    LLMModelRequest,
    LLMModelUpdateRequest,
    LLMSettingsResponse,
    MultimediaDigestRequest,
    ProviderSettingsRequest,
    ProviderSettingsResponse,
    SermonPrepRequest,
    TranscriptExportRequest,
    VerseCopilotRequest,
    DEFAULT_GUARDRAIL_SETTINGS,
)
from ...models.base import Passage as PassageSchema
from ...models.export import serialise_asset_content
from ...models.documents import DocumentDetailResponse
from ...models.export import (
    DocumentExportFilters,
    DocumentExportResponse,
)
from ...models.search import HybridSearchFilters
from ...intent.tagger import get_intent_tagger

_BAD_REQUEST_RESPONSE = {
    status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"}
}
_NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Resource not found"}
}
_BAD_REQUEST_NOT_FOUND_RESPONSES = {
    **_BAD_REQUEST_RESPONSE,
    **_NOT_FOUND_RESPONSE,
}


router = APIRouter()
settings_router = APIRouter(prefix="/settings/ai", tags=["ai-settings"])


LOGGER = logging.getLogger(__name__)

_MAX_STORED_MEMORY = 10
_MAX_CONTEXT_SNIPPETS = 4
_MEMORY_TEXT_LIMIT = 600
_MEMORY_SUMMARY_LIMIT = 400


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value.strip()
    truncated = value[: max(limit - 1, 0)].rstrip()
    return f"{truncated}…" if truncated else value[:limit]


def _has_filters(filters: HybridSearchFilters | None) -> bool:
    if not filters:
        return False
    return bool(filters.model_dump(exclude_none=True))


def _resolve_preferences(payload: ChatSessionRequest) -> ChatSessionPreferences:
    if payload.preferences:
        return payload.preferences
    default_filters = payload.filters if _has_filters(payload.filters) else None
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


@router.get("/features", response_model=AIFeaturesResponse)
def list_ai_features() -> AIFeaturesResponse:
    """Expose guardrail catalogues for client selection."""

    return AIFeaturesResponse(guardrails=DEFAULT_GUARDRAIL_SETTINGS)


def _persist_and_respond(
    session: Session, registry: LLMRegistry
) -> LLMSettingsResponse:
    save_llm_registry(session, registry)
    return LLMSettingsResponse(**registry.to_response())


def _extract_primary_topic(document: Document) -> str | None:
    """Return the primary topic for *document* when available."""

    if document.bib_json and isinstance(document.bib_json, dict):
        primary = document.bib_json.get("primary_topic")
        if isinstance(primary, str):
            return primary
    topics = document.topics
    if isinstance(topics, list) and topics:
        first = topics[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            value = first.get("primary")
            if isinstance(value, str):
                return value
    if isinstance(topics, dict):
        primary = topics.get("primary")
        if isinstance(primary, str):
            return primary
    return None


def _normalise_author(name: str) -> dict[str, str]:
    parts = [segment.strip() for segment in name.replace("  ", " ").split()] if name else []
    if "," in name:
        family, given = [segment.strip() for segment in name.split(",", 1)]
        if family and given:
            return {"given": given, "family": family}
    if len(parts) >= 2:
        return {"given": " ".join(parts[:-1]), "family": parts[-1]}
    return {"literal": name}


_CSL_TYPE_MAP = {
    "article": "article-journal",
    "journal": "article-journal",
    "book": "book",
    "video": "motion_picture",
    "audio": "song",
    "sermon": "speech",
    "web": "webpage",
}


def _infer_csl_type(source_type: str | None) -> str:
    if not source_type:
        return "article-journal"
    normalized = source_type.lower()
    for key, value in _CSL_TYPE_MAP.items():
        if key in normalized:
            return value
    return "article-journal"


def _build_csl_entry(
    record: Mapping[str, Any], citations: Sequence[RAGCitation]
) -> dict[str, Any]:
    authors: list[dict[str, str]] = []
    for name in record.get("authors") or []:
        if isinstance(name, str) and name.strip():
            authors.append(_normalise_author(name.strip()))

    entry: dict[str, Any] = {
        "id": record.get("document_id"),
        "type": _infer_csl_type(record.get("source_type")),
        "title": record.get("title"),
    }
    if authors:
        entry["author"] = authors
    year = record.get("year")
    if isinstance(year, int):
        entry["issued"] = {"date-parts": [[year]]}
    doi = record.get("doi")
    if isinstance(doi, str) and doi:
        entry["DOI"] = doi
    url = record.get("source_url")
    if isinstance(url, str) and url:
        entry["URL"] = url
    venue = record.get("venue")
    if isinstance(venue, str) and venue:
        entry["container-title"] = venue
    collection = record.get("collection")
    if isinstance(collection, str) and collection:
        entry["collection-title"] = collection
    abstract = record.get("abstract")
    if isinstance(abstract, str) and abstract:
        entry["abstract"] = abstract

    anchor_entries = []
    for citation in citations:
        anchor_label = f"{citation.osis} ({citation.anchor})" if citation.anchor else citation.osis
        anchor_entries.append(anchor_label)
    if anchor_entries:
        entry["note"] = "Anchors: " + "; ".join(anchor_entries)

    return entry


def _build_document_detail(
    document: Document,
    citations: Sequence[RAGCitation],
    passage_index: Mapping[str, Passage],
) -> DocumentDetailResponse:
    passages: list[PassageSchema] = []
    for citation in citations:
        passage = passage_index.get(citation.passage_id) if citation.passage_id else None
        if passage:
            meta = dict(passage.meta or {})
            meta.setdefault("anchor", citation.anchor)
            meta.setdefault("snippet", citation.snippet)
            passages.append(
                PassageSchema(
                    id=passage.id,
                    document_id=passage.document_id,
                    text=passage.text,
                    osis_ref=passage.osis_ref or citation.osis,
                    page_no=passage.page_no,
                    t_start=passage.t_start,
                    t_end=passage.t_end,
                    score=None,
                    meta=meta,
                )
            )
        else:
            passages.append(
                PassageSchema(
                    id=citation.passage_id or f"{citation.document_id}:{citation.index}",
                    document_id=citation.document_id,
                    text=citation.snippet,
                    osis_ref=citation.osis,
                    page_no=None,
                    t_start=None,
                    t_end=None,
                    score=None,
                    meta={"anchor": citation.anchor, "snippet": citation.snippet},
                )
            )

    title = document.title or (citations[0].document_title if citations else None)

    source_url = document.source_url
    for citation in citations:
        fields_set = getattr(citation, "model_fields_set", set())
        if "source_url" in fields_set:
            source_url = citation.source_url
            break

    return DocumentDetailResponse(
        id=document.id,
        title=title,
        source_type=document.source_type,
        collection=document.collection,
        authors=document.authors,
        doi=document.doi,
        venue=document.venue,
        year=document.year,
        created_at=document.created_at,
        updated_at=document.updated_at,
        source_url=source_url,
        channel=document.channel,
        video_id=document.video_id,
        duration_seconds=document.duration_seconds,
        storage_path=document.storage_path,
        abstract=document.abstract,
        topics=document.topics,
        enrichment_version=document.enrichment_version,
        primary_topic=_extract_primary_topic(document),
        provenance_score=document.provenance_score,
        meta=document.bib_json,
        passages=passages,
    )


@router.post(
    "/citations/export",
    response_model=CitationExportResponse,
    responses=_BAD_REQUEST_NOT_FOUND_RESPONSES,
)
def export_citations(
    payload: CitationExportRequest, session: Session = Depends(get_session)
) -> CitationExportResponse:
    """Return CSL-JSON and manager payloads for the supplied citations."""

    if not payload.citations:
        raise HTTPException(status_code=400, detail="citations cannot be empty")

    ordered_citations = sorted(payload.citations, key=lambda citation: citation.index)
    citation_map: dict[str, list[RAGCitation]] = {}
    document_order: list[str] = []
    for citation in ordered_citations:
        document_id = citation.document_id
        if not document_id:
            raise HTTPException(
                status_code=400, detail="citations must include a document_id"
            )
        bucket = citation_map.setdefault(document_id, [])
        bucket.append(citation)
        if document_id not in document_order:
            document_order.append(document_id)

    document_ids = list(citation_map.keys())
    rows = session.execute(
        select(Document).where(Document.id.in_(document_ids))
    ).scalars()
    document_index = {row.id: row for row in rows}
    missing_documents = [doc_id for doc_id in document_ids if doc_id not in document_index]
    if missing_documents:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown document(s): {', '.join(sorted(missing_documents))}",
        )

    passage_ids = {
        citation.passage_id
        for citation in ordered_citations
        if citation.passage_id is not None
    }
    passage_index: dict[str, Passage] = {}
    if passage_ids:
        passage_rows = session.execute(
            select(Passage).where(Passage.id.in_(passage_ids))
        ).scalars()
        passage_index = {row.id: row for row in passage_rows}

    document_details: list[DocumentDetailResponse] = []
    total_passages = 0
    for document_id in document_order:
        document = document_index[document_id]
        doc_citations = citation_map[document_id]
        detail = _build_document_detail(document, doc_citations, passage_index)
        total_passages += len(detail.passages)
        document_details.append(detail)

    export_payload = DocumentExportResponse(
        filters=DocumentExportFilters(),
        include_passages=True,
        limit=None,
        cursor=None,
        next_cursor=None,
        total_documents=len(document_details),
        total_passages=total_passages,
        documents=document_details,
    )
    manifest, records = build_document_export(
        export_payload,
        include_passages=True,
        include_text=False,
        fields=None,
        export_id=None,
    )
    record_dicts = [dict(record) for record in records]
    csl_entries: list[dict[str, Any]] = []
    for record in record_dicts:
        raw_document_id = record.get("document_id")
        citations = (
            citation_map.get(raw_document_id, [])
            if isinstance(raw_document_id, str)
            else []
        )
        csl_entries.append(_build_csl_entry(record, citations))
    manager_payload = {
        "format": "csl-json",
        "export_id": manifest.export_id,
        "zotero": {"items": csl_entries},
        "mendeley": {"documents": csl_entries},
    }

    return CitationExportResponse(
        manifest=manifest,
        records=record_dicts,
        csl=csl_entries,
        manager_payload=manager_payload,
    )


@router.get("/llm", response_model=LLMSettingsResponse)
def list_llm_models(session: Session = Depends(get_session)) -> LLMSettingsResponse:
    from . import get_llm_registry as _get_llm_registry
    registry = _get_llm_registry(session)
    return LLMSettingsResponse(**registry.to_response())


@router.post("/llm", response_model=LLMSettingsResponse, response_model_exclude_none=True)
def register_llm_model(
    payload: LLMModelRequest, session: Session = Depends(get_session)
) -> LLMSettingsResponse:
    from . import get_llm_registry as _get_llm_registry
    registry = _get_llm_registry(session)
    model = LLMModel(
        name=payload.name,
        provider=payload.provider,
        model=payload.model,
        config=dict(payload.config),
        pricing=dict(payload.pricing),
        latency=dict(payload.latency),
        routing=dict(payload.routing),
    )
    registry.add_model(model, make_default=payload.make_default)
    return _persist_and_respond(session, registry)


@router.patch(
    "/llm/default",
    response_model=LLMSettingsResponse,
    response_model_exclude_none=True,
    responses=_NOT_FOUND_RESPONSE,
)
def set_default_llm_model(
    payload: LLMDefaultRequest, session: Session = Depends(get_session)
) -> LLMSettingsResponse:
    from . import get_llm_registry as _get_llm_registry
    registry = _get_llm_registry(session)
    if payload.name not in registry.models:
        raise HTTPException(status_code=404, detail="Unknown model")
    registry.default_model = payload.name
    return _persist_and_respond(session, registry)


@router.patch(
    "/llm/{name}",
    response_model=LLMSettingsResponse,
    response_model_exclude_none=True,
    responses=_NOT_FOUND_RESPONSE,
)
def update_llm_model(
    name: str, payload: LLMModelUpdateRequest, session: Session = Depends(get_session)
) -> LLMSettingsResponse:
    from . import get_llm_registry as _get_llm_registry
    registry = _get_llm_registry(session)
    if name not in registry.models:
        raise HTTPException(status_code=404, detail="Unknown model")
    model = registry.models[name]
    if payload.provider:
        model.provider = payload.provider
    if payload.model:
        model.model = payload.model
    if payload.config is not None:
        for key, value in dict(payload.config).items():
            if value is None:
                model.config.pop(key, None)
            else:
                model.config[key] = value
    if payload.pricing is not None:
        for key, value in dict(payload.pricing).items():
            if value is None:
                model.pricing.pop(key, None)
            else:
                model.pricing[key] = value
    if payload.latency is not None:
        for key, value in dict(payload.latency).items():
            if value is None:
                model.latency.pop(key, None)
            else:
                model.latency[key] = value
    if payload.routing is not None:
        for key, value in dict(payload.routing).items():
            if value is None:
                model.routing.pop(key, None)
            else:
                model.routing[key] = value
    if payload.make_default:
        registry.default_model = name
    return _persist_and_respond(session, registry)


@router.delete(
    "/llm/{name}",
    response_model=LLMSettingsResponse,
    response_model_exclude_none=True,
    responses=_NOT_FOUND_RESPONSE,
)
def remove_llm_model(name: str, session: Session = Depends(get_session)) -> LLMSettingsResponse:
    from . import get_llm_registry as _get_llm_registry
    registry = _get_llm_registry(session)
    if name not in registry.models:
        raise HTTPException(status_code=404, detail="Unknown model")
    registry.remove_model(name)
    return _persist_and_respond(session, registry)


CHAT_PLAN = "\n".join(
    [
        "- Retrieve supporting passages using hybrid search",
        "- Compose a grounded assistant reply with citations",
        "- Validate guardrails before finalising the turn",
    ]
)


_DEFAULT_REFUSAL_MESSAGE = "I’m sorry, but I cannot help with that request."


def _normalise_filters_for_advisory(
    filters: HybridSearchFilters | None,
) -> HybridSearchFilters | None:
    """Remove empty guardrail filters before serialising suggestions."""

    if filters is None:
        return None
    data = filters.model_dump(exclude_none=True)
    if not data:
        return None
    return HybridSearchFilters(**data)
_GUARDRAIL_KIND_MAP = {
    "retrieval": "retrieval",
    "generation": "generation",
    "safety": "safety",
    "ingest": "ingest",
}

_SUGGESTED_ACTIONS = {"search", "upload", "retry", "none"}


def _coerce_filters(value: object) -> HybridSearchFilters | None:
    if isinstance(value, HybridSearchFilters):
        return value if _has_filters(value) else None
    if isinstance(value, Mapping):
        try:
            candidate = HybridSearchFilters.model_validate(value)
        except Exception:  # pragma: no cover - defensive
            return None
        return candidate if _has_filters(candidate) else None
    return None


def _build_guardrail_metadata(
    exc: GuardrailError, filters: HybridSearchFilters | None
) -> GuardrailFailureMetadata:
    raw_metadata = getattr(exc, "metadata", None)
    payload: Mapping[str, Any] | None = None
    if isinstance(raw_metadata, Mapping):
        payload = raw_metadata
    elif isinstance(raw_metadata, dict):
        payload = raw_metadata

    code = "guardrail_violation"
    guardrail_value = "unknown"
    suggested_action = None
    reason: str | None = None
    embedded_filters: HybridSearchFilters | None = None

    if payload:
        if "code" in payload and isinstance(payload["code"], str):
            code = payload["code"].strip() or code
        raw_guardrail = payload.get("guardrail") or payload.get("category")
        if isinstance(raw_guardrail, str):
            guardrail_key = raw_guardrail.strip().lower()
            guardrail_value = _GUARDRAIL_KIND_MAP.get(guardrail_key, "unknown")
        raw_action = payload.get("suggested_action") or payload.get("action")
        if isinstance(raw_action, str):
            candidate_action = raw_action.strip().lower()
            if candidate_action in _SUGGESTED_ACTIONS:
                suggested_action = candidate_action
        raw_reason = payload.get("reason")
        if raw_reason is not None:
            reason = str(raw_reason)
        embedded_filters = _coerce_filters(payload.get("filters"))

    resolved_filters = _normalise_filters_for_advisory(embedded_filters or filters)

    if suggested_action not in _SUGGESTED_ACTIONS:
        if guardrail_value == "ingest":
            suggested_action = "upload"
        else:
            suggested_action = "search"

    return GuardrailFailureMetadata(
        code=code,
        guardrail=guardrail_value,  # type: ignore[arg-type]
        suggested_action=suggested_action,  # type: ignore[arg-type]
        filters=resolved_filters,
        safe_refusal=getattr(exc, "safe_refusal", False),
        reason=reason,
    )


def _guardrail_advisory(
    message: str,
    *,
    question: str | None,
    osis: str | None,
    filters: HybridSearchFilters | None,
    metadata: GuardrailFailureMetadata | None,
) -> GuardrailAdvisory:
    """Build a structured guardrail response with actionable follow-ups."""

    failure_metadata = metadata or GuardrailFailureMetadata(
        code="guardrail_violation",
        guardrail="unknown",
        suggested_action="search",
        filters=_normalise_filters_for_advisory(filters),
        safe_refusal=False,
        reason=None,
    )

    normalized_filters = failure_metadata.filters or _normalise_filters_for_advisory(filters)
    if normalized_filters is not None:
        failure_metadata = failure_metadata.model_copy(update={"filters": normalized_filters})

    suggestions: list[GuardrailSuggestion] = []

    if failure_metadata.suggested_action in {"search", "retry", "none", "upload"}:
        suggestions.append(
            GuardrailSuggestion(
                action="search",
                label="Search related passages",
                description=(
                    "Open the search workspace to inspect passages that align with your question and guardrail settings."
                ),
                query=question or None,
                osis=osis or None,
                filters=normalized_filters,
            )
        )

    if failure_metadata.suggested_action == "upload":
        suggestions.append(
            GuardrailSuggestion(
                action="upload",
                label="Upload supporting documents",
                description=(
                    "Add source material to your corpus so Theo Engine can ground future answers."
                ),
                collection=(
                    normalized_filters.collection if normalized_filters else None
                ),
            )
        )

    return GuardrailAdvisory(
        message=message,
        suggestions=suggestions,
        metadata=failure_metadata,
    )


def _guardrail_http_exception(
    exc: GuardrailError,
    *,
    session: Session,
    question: str | None,
    osis: str | None,
    filters: HybridSearchFilters | None,
) -> JSONResponse:
    failure_metadata = _build_guardrail_metadata(exc, filters)
    advisory = _guardrail_advisory(
        str(exc),
        question=question,
        osis=osis,
        filters=filters,
        metadata=failure_metadata,
    )
    summary = str(exc).strip() or "Guardrail enforcement prevented a response."
    detail_text = f"Guardrail refusal: {summary}"
    advisory_payload = advisory.model_dump(mode="json")
    advisory_payload.update({"type": "guardrail_refusal", "message": summary})
    detail_payload = {
        "type": advisory_payload.get("type"),
        "message": detail_text,
        "summary": summary,
        "metadata": advisory_payload.get("metadata"),
        "suggestions": advisory_payload.get("suggestions") or [],
    }
    answer = build_guardrail_refusal(session, reason=summary)
    headers = {
        "X-Guardrail-Advisory": json.dumps(
            advisory_payload, separators=(",", ":")
        )
    }
    content = {
        "detail": detail_payload,
        "message": {"role": "assistant", "content": _DEFAULT_REFUSAL_MESSAGE},
        "answer": answer.model_dump(mode="json"),
        "guardrail_advisory": advisory_payload,
        "detail_text": detail_text,
    }
    return JSONResponse(status_code=422, content=content, headers=headers)


def _extract_refusal_text(answer: RAGAnswer) -> str:
    """Normalise a guardrailed completion for user-facing chat responses."""

    completion = answer.model_output or ""
    if completion:
        lowered = completion.lower()
        marker_index = lowered.rfind("sources:")
        if marker_index != -1:
            completion = completion[:marker_index]
        completion = completion.strip()
    if not completion:
        completion = (answer.summary or "").strip()
    if not completion:
        completion = _DEFAULT_REFUSAL_MESSAGE
    return completion


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

            message_text = _extract_refusal_text(answer)
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
        return _guardrail_http_exception(
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


_PROVIDER_SETTINGS_KEY = "ai_providers"
_PROVIDER_FIELDS = {"api_key", "base_url", "default_model", "extra_headers"}


def _load_provider_settings(session: Session) -> dict[str, dict[str, object]]:
    payload = load_setting(session, _PROVIDER_SETTINGS_KEY, default={})
    if not isinstance(payload, dict):
        return {}
    settings: dict[str, dict[str, object]] = {}
    for provider, raw in payload.items():
        if not isinstance(provider, str) or not isinstance(raw, dict):
            continue
        normalized: dict[str, object] = {}
        for key in _PROVIDER_FIELDS:
            if key not in raw:
                continue
            value = raw[key]
            if key == "extra_headers":
                if isinstance(value, dict):
                    normalized[key] = {
                        str(h_key): str(h_value)
                        for h_key, h_value in value.items()
                        if isinstance(h_key, str) and isinstance(h_value, str)
                    }
                continue
            normalized[key] = value
        settings[provider] = normalized
    return settings


def _store_provider_settings(
    session: Session, providers: dict[str, dict[str, object]]
) -> None:
    save_setting(session, _PROVIDER_SETTINGS_KEY, providers)


def _provider_response(
    provider: str, payload: dict[str, object] | None
) -> ProviderSettingsResponse:
    payload = payload or {}
    headers = payload.get("extra_headers")
    normalized_headers: dict[str, str] | None = None
    if isinstance(headers, dict):
        normalized_headers = {
            str(key): str(value)
            for key, value in headers.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    base_url_value = payload.get("base_url")
    default_model_value = payload.get("default_model")
    return ProviderSettingsResponse(
        provider=provider,
        base_url=base_url_value if isinstance(base_url_value, str) else None,
        default_model=(
            default_model_value if isinstance(default_model_value, str) else None
        ),
        extra_headers=normalized_headers,
        has_api_key=bool(payload.get("api_key")),
    )


@settings_router.get(
    "/providers",
    response_model=list[ProviderSettingsResponse],
    response_model_exclude_none=True,
)
def list_providers(session: Session = Depends(get_session)) -> list[ProviderSettingsResponse]:
    providers = _load_provider_settings(session)
    return [
        _provider_response(name, payload)
        for name, payload in sorted(providers.items())
    ]


@settings_router.get(
    "/providers/{provider}",
    response_model=ProviderSettingsResponse,
    response_model_exclude_none=True,
    responses=_NOT_FOUND_RESPONSE,
)
def get_provider_settings(
    provider: str, session: Session = Depends(get_session)
) -> ProviderSettingsResponse:
    providers = _load_provider_settings(session)
    payload = providers.get(provider)
    if payload is None:
        raise HTTPException(status_code=404, detail="Provider not configured")
    return _provider_response(provider, payload)


@settings_router.put(
    "/providers/{provider}",
    response_model=ProviderSettingsResponse,
    response_model_exclude_none=True,
)
def upsert_provider_settings(
    provider: str,
    payload: ProviderSettingsRequest,
    session: Session = Depends(get_session),
) -> ProviderSettingsResponse:
    providers = _load_provider_settings(session)
    existing = providers.get(provider, {}).copy()
    update_data = payload.model_dump(exclude_unset=True)
    for field in ("base_url", "default_model"):
        if field in update_data:
            value = update_data[field]
            if value is None:
                existing.pop(field, None)
            elif isinstance(value, str) and value:
                existing[field] = value
            else:
                existing.pop(field, None)
    if "extra_headers" in update_data:
        headers = update_data["extra_headers"]
        if headers is None:
            existing.pop("extra_headers", None)
        elif isinstance(headers, dict):
            existing["extra_headers"] = {
                str(key): str(value)
                for key, value in headers.items()
                if isinstance(key, str) and isinstance(value, str)
            }
    if "api_key" in update_data:
        api_key = update_data["api_key"]
        if api_key is None or (isinstance(api_key, str) and not api_key):
            existing.pop("api_key", None)
        elif isinstance(api_key, str):
            existing["api_key"] = api_key
    providers[provider] = existing
    _store_provider_settings(session, providers)
    return _provider_response(provider, existing)


@settings_router.delete(
    "/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
def delete_provider_settings(
    provider: str, session: Session = Depends(get_session)
) -> Response:
    providers = _load_provider_settings(session)
    if provider in providers:
        providers.pop(provider)
        _store_provider_settings(session, providers)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


VERSE_COPILOT_PLAN = "\n".join(
    [
        "- Retrieve relevant passages with hybrid search",
        "- Generate a grounded answer with the configured LLM",
        "- Return citations and recommended follow-up prompts",
    ]
)

SERMON_PREP_PLAN = "\n".join(
    [
        "- Search for passages aligned to the sermon topic",
        "- Summarise retrieved context into a guardrailed outline",
        "- Surface key points and citations for sermon preparation",
    ]
)

MULTIMEDIA_PLAN = "\n".join(
    [
        "- Retrieve recent multimedia passages with hybrid search",
        "- Summarise cross-media highlights with the configured LLM",
        "- Return grounded insights with supporting citations",
    ]
)

DEVOTIONAL_PLAN = "\n".join(
    [
        "- Retrieve reflective passages tied to the devotional focus",
        "- Compose a prayerful reflection grounded in citations",
        "- Suggest prayer prompts rooted in retrieved passages",
    ]
)

COLLABORATION_PLAN = "\n".join(
    [
        "- Gather sources representing each supplied viewpoint",
        "- Reconcile perspectives using a grounded synthesis",
        "- Surface shared insights with cited support",
    ]
)

CORPUS_CURATION_PLAN = "\n".join(
    [
        "- Load documents added within the requested window",
        "- Summarise each document by topic and collection",
        "- Produce a curator-ready digest of repository changes",
    ]
)


@router.post("/verse", response_model_exclude_none=True)
def verse_copilot(
    payload: VerseCopilotRequest,
    session: Session = Depends(get_session),
):
    trail_service = TrailService(session)
    osis_value = (payload.osis or "").strip() or None
    passage_value = (payload.passage or "").strip() or None
    try:
        resolved_osis = osis_value or (
            resolve_passage_reference(passage_value) if passage_value else None
        )
    except PassageResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not resolved_osis:
        raise HTTPException(status_code=422, detail="Provide an OSIS reference or passage.")
    try:
        with trail_service.start_trail(
            workflow="verse_copilot",
            plan_md=VERSE_COPILOT_PLAN,
            mode="verse_copilot",
            input_payload=payload.model_dump(mode="json"),
            user_id=(
                payload.recorder_metadata.user_id
                if payload.recorder_metadata
                else None
            ),
        ) as recorder:
            response = generate_verse_brief(
                session,
                osis=resolved_osis,
                question=payload.question,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(final_md=response.answer.summary, output_payload=response)
            return response
    except GuardrailError as exc:
        return _guardrail_http_exception(
            exc,
            session=session,
            question=payload.question,
            osis=resolved_osis,
            filters=payload.filters,
        )


@router.post("/sermon-prep", response_model_exclude_none=True)
def sermon_prep(
    payload: SermonPrepRequest,
    session: Session = Depends(get_session),
):
    trail_service = TrailService(session)
    try:
        with trail_service.start_trail(
            workflow="sermon_prep",
            plan_md=SERMON_PREP_PLAN,
            mode="sermon_prep",
            input_payload=payload.model_dump(mode="json"),
            user_id=(
                payload.recorder_metadata.user_id
                if payload.recorder_metadata
                else None
            ),
        ) as recorder:
            response = generate_sermon_prep_outline(
                session,
                topic=payload.topic,
                osis=payload.osis,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(final_md=response.answer.summary, output_payload=response)
            return response
    except GuardrailError as exc:
        return _guardrail_http_exception(
            exc,
            session=session,
            question=None,
            osis=payload.osis,
            filters=payload.filters,
        )


# FastAPI coerces literal return types when a response model is provided, so we
# rely on the schema class directly for OpenAPI generation.
@router.post("/sermon-prep/export", response_model=ExportDeliverableResponse)
def sermon_prep_export(
    payload: SermonPrepRequest,
    format: str = Query(
        default="markdown", description="markdown, ndjson, csv, or pdf"
    ),
    session: Session = Depends(get_session),
) -> ExportDeliverableResponse:
    try:
        response = generate_sermon_prep_outline(
            session,
            topic=payload.topic,
            osis=payload.osis,
            filters=payload.filters,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        return _guardrail_http_exception(
            exc,
            session=session,
            question=None,
            osis=payload.osis,
            filters=payload.filters,
        )
    normalized = format.lower()
    package = build_sermon_deliverable(
        response,
        formats=[normalized],
        filters=payload.filters.model_dump(exclude_none=True),
    )
    try:
        preset = _SERMON_PRESET_MAP[normalized]
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="unsupported sermon export format") from exc
    asset = package.get_asset(normalized)
    return ExportDeliverableResponse(
        preset=preset,
        format=asset.format,
        filename=asset.filename,
        media_type=asset.media_type,
        content=serialise_asset_content(asset.content),
    )

# See comment above regarding the response model.
@router.post("/transcript/export", response_model=ExportDeliverableResponse)
 
def transcript_export(
    payload: TranscriptExportRequest,
    session: Session = Depends(get_session),
) -> ExportDeliverableResponse:
    normalized = payload.format.lower()
    try:
        package = build_transcript_deliverable(
            session, payload.document_id, formats=[normalized]
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        preset = _TRANSCRIPT_PRESET_MAP[normalized]
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="unsupported transcript export format") from exc
    asset = package.get_asset(normalized)
    return ExportDeliverableResponse(
        preset=preset,
        format=asset.format,
        filename=asset.filename,
        media_type=asset.media_type,
        content=serialise_asset_content(asset.content),
    )


@router.post(
    "/comparative",
    response_model_exclude_none=True,
    responses=_BAD_REQUEST_RESPONSE,
)
def comparative_analysis(
    payload: ComparativeAnalysisRequest,
    session: Session = Depends(get_session),
):
    if not payload.participants:
        raise HTTPException(status_code=400, detail="participants cannot be empty")
    try:
        return generate_comparative_analysis(
            session,
            osis=payload.osis,
            participants=payload.participants,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        return _guardrail_http_exception(
            exc,
            session=session,
            question=None,
            osis=payload.osis,
            filters=None,
        )


@router.post("/multimedia", response_model_exclude_none=True)
def multimedia_digest(
    payload: MultimediaDigestRequest,
    session: Session = Depends(get_session),
):
    trail_service = TrailService(session)
    try:
        with trail_service.start_trail(
            workflow="multimedia_digest",
            plan_md=MULTIMEDIA_PLAN,
            mode="multimedia_digest",
            input_payload=payload.model_dump(mode="json"),
            user_id=None,
        ) as recorder:
            response = generate_multimedia_digest(
                session,
                collection=payload.collection,
                model_name=payload.model,
                recorder=recorder,
            )
            final_md = response.answer.summary or "\n".join(response.highlights)
            recorder.finalize(final_md=final_md, output_payload=response)
            return response
    except GuardrailError as exc:
        return _guardrail_http_exception(
            exc,
            session=session,
            question=payload.collection,
            osis=None,
            filters=None,
        )


@router.post("/devotional", response_model_exclude_none=True)
def devotional_flow(
    payload: DevotionalRequest,
    session: Session = Depends(get_session),
):
    trail_service = TrailService(session)
    try:
        with trail_service.start_trail(
            workflow="devotional",
            plan_md=DEVOTIONAL_PLAN,
            mode="devotional",
            input_payload=payload.model_dump(mode="json"),
            user_id=None,
        ) as recorder:
            response = generate_devotional_flow(
                session,
                osis=payload.osis,
                focus=payload.focus,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(
                final_md=response.reflection,
                output_payload=response,
            )
            return response
    except GuardrailError as exc:
        return _guardrail_http_exception(
            exc,
            session=session,
            question=payload.focus,
            osis=payload.osis,
            filters=None,
        )


@router.post(
    "/collaboration",
    response_model_exclude_none=True,
    responses=_BAD_REQUEST_RESPONSE,
)
def collaboration(
    payload: CollaborationRequest,
    session: Session = Depends(get_session),
):
    if not payload.viewpoints:
        raise HTTPException(status_code=400, detail="viewpoints cannot be empty")
    trail_service = TrailService(session)
    try:
        with trail_service.start_trail(
            workflow="research_reconciliation",
            plan_md=COLLABORATION_PLAN,
            mode="collaboration",
            input_payload=payload.model_dump(mode="json"),
            user_id=None,
        ) as recorder:
            response = run_research_reconciliation(
                session,
                thread=payload.thread,
                osis=payload.osis,
                viewpoints=payload.viewpoints,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(
                final_md=response.synthesized_view,
                output_payload=response,
            )
            return response
    except GuardrailError as exc:
        return _guardrail_http_exception(
            exc,
            session=session,
            question="; ".join(payload.viewpoints) if payload.viewpoints else None,
            osis=payload.osis,
            filters=None,
        )


@router.post(
    "/curation",
    response_model_exclude_none=True,
    responses=_BAD_REQUEST_RESPONSE,
)
def corpus_curation(
    payload: CorpusCurationRequest,
    session: Session = Depends(get_session),
):
    since_dt = None
    if payload.since:
        try:
            since_dt = datetime.fromisoformat(payload.since)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="since must be ISO formatted"
            ) from exc
    trail_service = TrailService(session)
    with trail_service.start_trail(
        workflow="corpus_curation",
        plan_md=CORPUS_CURATION_PLAN,
        mode="corpus_curation",
        input_payload=payload.model_dump(mode="json"),
        user_id=None,
    ) as recorder:
        response = run_corpus_curation(session, since=since_dt, recorder=recorder)
        digest = "\n".join(response.summaries)
        recorder.finalize(final_md=digest or None, output_payload=response)
        return response


_SERMON_PRESET_MAP: dict[str, ExportPresetId] = {
    "markdown": "sermon-markdown",
    "ndjson": "sermon-ndjson",
    "csv": "sermon-csv",
    "pdf": "sermon-pdf",
}

_TRANSCRIPT_PRESET_MAP: dict[str, ExportPresetId] = {
    "markdown": "transcript-markdown",
    "csv": "transcript-csv",
    "pdf": "transcript-pdf",
}

