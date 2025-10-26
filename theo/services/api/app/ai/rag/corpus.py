"""Corpus curation orchestration helpers for guardrailed RAG flows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.services.api.app.persistence_models import Document

from theo.application.facades.telemetry import (
    instrument_workflow,
    log_workflow_event,
    set_span_attribute,
)
from .models import CorpusCurationReport

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..trails import TrailRecorder


__all__ = ["run_corpus_curation"]


def run_corpus_curation(
    session: Session,
    *,
    since: datetime | None = None,
    recorder: "TrailRecorder | None" = None,
) -> CorpusCurationReport:
    """Summarise recent corpus additions for researcher review."""

    with instrument_workflow(
        "corpus_curation",
        since=since.isoformat() if since else "auto-7d",
    ) as span:
        if since is None:
            since = datetime.now(UTC) - timedelta(days=7)
        set_span_attribute(span, "workflow.effective_since", since.isoformat())
        try:
            query = (
                select(Document)
                .where(Document.created_at >= since)
                .order_by(Document.created_at.asc())
            )
            rows = session.execute(query).scalars().all()
        except NotImplementedError:
            rows = []
        set_span_attribute(span, "workflow.documents_processed", len(rows))
        log_workflow_event(
            "workflow.documents_loaded",
            workflow="corpus_curation",
            count=len(rows),
        )
        summaries: list[str] = []
        for document in rows:
            primary_topic = None
            if document.bib_json and isinstance(document.bib_json, dict):
                primary_topic = document.bib_json.get("primary_topic")
            if isinstance(document.topics, list) and not primary_topic:
                primary_topic = document.topics[0] if document.topics else None
            topic_label = primary_topic or "Uncategorised"
            summaries.append(
                f"{document.title or document.id} — {topic_label} ({document.collection or 'general'})"
            )
        set_span_attribute(span, "workflow.summary_count", len(summaries))
        if recorder:
            recorder.log_step(
                tool="corpus_curation",
                action="summarise_documents",
                input_payload={"since": since.isoformat()},
                output_payload=summaries,
                output_digest=f"{len(summaries)} summaries",
            )
        return CorpusCurationReport(
            since=since, documents_processed=len(rows), summaries=summaries
        )
