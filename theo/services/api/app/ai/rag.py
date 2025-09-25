"""Guardrailed RAG workflows for Theo Engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Document, Passage
from ..models.base import APIModel
from ..models.search import HybridSearchFilters, HybridSearchRequest, HybridSearchResult
from ..retriever.hybrid import hybrid_search
from ..core.version import get_git_sha
from .clients import GenerationError
from .registry import LLMRegistry, get_llm_registry

if TYPE_CHECKING:  # pragma: no cover - hints only
    from .trails import TrailRecorder


class GuardrailError(GenerationError):
    """Raised when an answer violates grounding requirements."""


class RAGCitation(APIModel):
    index: int
    osis: str
    anchor: str
    passage_id: str
    document_id: str
    document_title: str | None = None
    snippet: str


class RAGAnswer(APIModel):
    summary: str
    citations: list[RAGCitation]
    model_name: str | None = None
    model_output: str | None = None


class VerseCopilotResponse(APIModel):
    osis: str
    question: str | None = None
    answer: RAGAnswer
    follow_ups: list[str]


class SermonPrepResponse(APIModel):
    topic: str
    osis: str | None = None
    outline: list[str]
    key_points: list[str]
    answer: RAGAnswer


class ComparativeAnalysisResponse(APIModel):
    osis: str
    participants: list[str]
    comparisons: list[str]
    answer: RAGAnswer


class MultimediaDigestResponse(APIModel):
    collection: str | None
    highlights: list[str]
    answer: RAGAnswer


class DevotionalResponse(APIModel):
    osis: str
    focus: str
    reflection: str
    prayer: str
    answer: RAGAnswer


class CorpusCurationReport(APIModel):
    since: datetime
    documents_processed: int
    summaries: list[str]


class CollaborationResponse(APIModel):
    thread: str
    synthesized_view: str
    answer: RAGAnswer


def _format_anchor(passage: HybridSearchResult | Passage) -> str:
    if getattr(passage, "page_no", None) is not None:
        return f"page {passage.page_no}"
    if getattr(passage, "t_start", None) is not None:
        t_end = getattr(passage, "t_end", None)
        if t_end is None:
            return f"t={passage.t_start:.0f}s"
        return f"t={passage.t_start:.0f}-{t_end:.0f}s"
    return "context"


def _build_citations(results: Sequence[HybridSearchResult]) -> list[RAGCitation]:
    citations: list[RAGCitation] = []
    for index, result in enumerate(results, start=1):
        if not result.osis_ref:
            continue
        anchor = _format_anchor(result)
        snippet = (result.snippet or result.text).strip()
        citations.append(
            RAGCitation(
                index=index,
                osis=result.osis_ref,
                anchor=anchor,
                passage_id=result.id,
                document_id=result.document_id,
                document_title=result.document_title,
                snippet=snippet,
            )
        )
    return citations


def _guarded_answer(
    session: Session,
    *,
    question: str | None,
    results: Sequence[HybridSearchResult],
    registry: LLMRegistry,
    model_hint: str | None = None,
    recorder: "TrailRecorder | None" = None,
) -> RAGAnswer:
    citations = _build_citations(results)
    if not citations:
        raise GuardrailError("Retrieved passages lacked OSIS references; aborting generation")

    summary_lines = []
    for citation, result in zip(citations, results):
        summary_lines.append(
            f"[{citation.index}] {citation.snippet} — {citation.document_title or citation.document_id}"
            f" ({citation.osis}, {citation.anchor})"
        )
    summary_text = "\n".join(summary_lines)

    model_output = None
    model_name = None
    try:
        model = registry.get(model_hint)
    except GenerationError:
        model = None

    if model:
        context_lines = [
            f"[{citation.index}] {citation.snippet} (OSIS {citation.osis}, {citation.anchor})"
            for citation in citations
        ]
        prompt_parts = [
            "You are Theo Engine's grounded assistant.",
            "Answer the question strictly from the provided passages.",
            "Cite evidence using the bracketed indices and retain OSIS + anchor in a Sources line.",
            "If the passages do not answer the question, state that explicitly.",
        ]
        if question:
            prompt_parts.append(f"Question: {question}")
        prompt_parts.append("Passages:")
        prompt_parts.extend(context_lines)
        prompt_parts.append("Respond with 2-3 sentences followed by 'Sources:'")
        prompt = "\n".join(prompt_parts)
        client = model.build_client()
        llm_payload = {
            "prompt": prompt,
            "model": model.model,
            "registry_name": model.name,
        }
        try:
            completion = client.generate(prompt=prompt, model=model.model)
        except GenerationError as exc:
            if recorder:
                recorder.log_step(
                    tool="llm.generate",
                    action="generate_grounded_answer",
                    status="failed",
                    input_payload=llm_payload,
                    output_digest=str(exc),
                    error_message=str(exc),
                )
            completion = None
        else:
            if recorder:
                recorder.log_step(
                    tool="llm.generate",
                    action="generate_grounded_answer",
                    input_payload=llm_payload,
                    output_payload={"completion": completion},
                    output_digest=f"{len(completion)} characters",
                )
            sources_line = "; ".join(
                f"[{citation.index}] {citation.osis} ({citation.anchor})" for citation in citations
            )
            if "Sources:" not in completion:
                completion = completion.strip() + f"\n\nSources: {sources_line}"
            model_output = completion
            model_name = model.name

    if recorder:
        recorder.log_step(
            tool="rag.compose",
            action="compose_answer",
            input_payload={
                "question": question,
                "citations": [
                    {
                        "index": citation.index,
                        "osis": citation.osis,
                        "anchor": citation.anchor,
                        "snippet": citation.snippet,
                        "passage_id": citation.passage_id,
                    }
                    for citation in citations
                ],
            },
            output_payload={
                "summary": summary_text,
                "model_name": model_name,
                "model_output": model_output,
            },
            output_digest=f"{len(summary_lines)} summary lines",
        )

    return RAGAnswer(summary=summary_text, citations=citations, model_name=model_name, model_output=model_output)


def _search(session: Session, *, query: str | None, osis: str | None, filters: HybridSearchFilters, k: int = 8) -> list[HybridSearchResult]:
    request = HybridSearchRequest(query=query, osis=osis, filters=filters, k=k)
    return hybrid_search(session, request)


def generate_verse_brief(
    session: Session,
    *,
    osis: str,
    question: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
) -> VerseCopilotResponse:
    filters = filters or HybridSearchFilters()
    results = _search(session, query=question or osis, osis=osis, filters=filters)
    registry = get_llm_registry(session)
    if recorder:
        recorder.log_step(
            tool="hybrid_search",
            action="retrieve_passages",
            input_payload={
                "query": question or osis,
                "osis": osis,
                "filters": filters,
            },
            output_payload=[
                {
                    "id": result.id,
                    "osis": result.osis_ref,
                    "document_id": result.document_id,
                    "score": getattr(result, "score", None),
                    "snippet": result.snippet,
                }
                for result in results
            ],
            output_digest=f"{len(results)} passages",
        )
    answer = _guarded_answer(
        session,
        question=question,
        results=results,
        registry=registry,
        model_hint=model_name,
        recorder=recorder,
    )
    if recorder:
        recorder.record_citations(answer.citations)
    follow_ups = [
        "Compare historical and contemporary commentary",
        "Trace how this verse links to adjacent passages",
        "Surface sermons that emphasise this verse",
    ]
    return VerseCopilotResponse(osis=osis, question=question, answer=answer, follow_ups=follow_ups)


def generate_sermon_prep_outline(
    session: Session,
    *,
    topic: str,
    osis: str | None = None,
    filters: HybridSearchFilters | None = None,
    model_name: str | None = None,
    recorder: "TrailRecorder | None" = None,
) -> SermonPrepResponse:
    filters = filters or HybridSearchFilters()
    query = topic if not osis else f"{topic} {osis}"
    results = _search(session, query=query, osis=osis, filters=filters, k=10)
    registry = get_llm_registry(session)
    if recorder:
        recorder.log_step(
            tool="hybrid_search",
            action="retrieve_passages",
            input_payload={
                "query": query,
                "osis": osis,
                "filters": filters,
            },
            output_payload=[
                {
                    "id": result.id,
                    "osis": result.osis_ref,
                    "document_id": result.document_id,
                    "score": getattr(result, "score", None),
                    "snippet": result.snippet,
                }
                for result in results
            ],
            output_digest=f"{len(results)} passages",
        )
    answer = _guarded_answer(
        session,
        question=query,
        results=results,
        registry=registry,
        model_hint=model_name,
        recorder=recorder,
    )
    if recorder:
        recorder.record_citations(answer.citations)
    outline = [
        "Opening: situate the passage within the wider canon",
        "Exposition: unpack key theological moves in the passages",
        "Application: connect the insights to contemporary discipleship",
        "Closing: invite response grounded in the cited witnesses",
    ]
    key_points = [f"{citation.osis}: {citation.snippet}" for citation in answer.citations[:4]]
    return SermonPrepResponse(topic=topic, osis=osis, outline=outline, key_points=key_points, answer=answer)


def generate_comparative_analysis(
    session: Session,
    *,
    osis: str,
    participants: Sequence[str],
    model_name: str | None = None,
) -> ComparativeAnalysisResponse:
    filters = HybridSearchFilters()
    results = _search(session, query="; ".join(participants), osis=osis, filters=filters, k=12)
    registry = get_llm_registry(session)
    answer = _guarded_answer(
        session,
        question=f"How do {', '.join(participants)} interpret {osis}?",
        results=results,
        registry=registry,
        model_hint=model_name,
    )
    comparisons = []
    for citation in answer.citations:
        comparisons.append(f"{citation.document_title or citation.document_id}: {citation.snippet}")
    return ComparativeAnalysisResponse(osis=osis, participants=list(participants), comparisons=comparisons, answer=answer)


def generate_multimedia_digest(
    session: Session,
    *,
    collection: str | None = None,
    model_name: str | None = None,
) -> MultimediaDigestResponse:
    filters = HybridSearchFilters(collection=collection, source_type="audio" if collection else None)
    results = _search(session, query="highlights", osis=None, filters=filters, k=8)
    registry = get_llm_registry(session)
    answer = _guarded_answer(session, question="What are the key audio/video insights?", results=results, registry=registry, model_hint=model_name)
    highlights = [f"{citation.document_title or citation.document_id}: {citation.snippet}" for citation in answer.citations]
    return MultimediaDigestResponse(collection=collection, highlights=highlights, answer=answer)


def generate_devotional_flow(
    session: Session,
    *,
    osis: str,
    focus: str,
    model_name: str | None = None,
) -> DevotionalResponse:
    filters = HybridSearchFilters()
    results = _search(session, query=focus, osis=osis, filters=filters, k=6)
    registry = get_llm_registry(session)
    answer = _guarded_answer(session, question=f"Devotional focus: {focus}", results=results, registry=registry, model_hint=model_name)
    reflection = "\n".join(f"Reflect on {citation.osis} ({citation.anchor}): {citation.snippet}" for citation in answer.citations[:3])
    prayer_lines = [f"Spirit, help me embody {citation.snippet}" for citation in answer.citations[:2]]
    prayer = "\n".join(prayer_lines)
    return DevotionalResponse(osis=osis, focus=focus, reflection=reflection, prayer=prayer, answer=answer)


def run_corpus_curation(
    session: Session,
    *,
    since: datetime | None = None,
) -> CorpusCurationReport:
    if since is None:
        since = datetime.now(UTC) - timedelta(days=7)
    rows = (
        session.execute(
            select(Document).where(Document.created_at >= since).order_by(Document.created_at.asc())
        ).scalars().all()
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
    return CorpusCurationReport(since=since, documents_processed=len(rows), summaries=summaries)


def run_research_reconciliation(
    session: Session,
    *,
    thread: str,
    osis: str,
    viewpoints: Sequence[str],
    model_name: str | None = None,
) -> CollaborationResponse:
    filters = HybridSearchFilters()
    results = _search(session, query="; ".join(viewpoints), osis=osis, filters=filters, k=10)
    registry = get_llm_registry(session)
    answer = _guarded_answer(
        session,
        question=f"Reconcile viewpoints for {osis} in {thread}",
        results=results,
        registry=registry,
        model_hint=model_name,
    )
    synthesis_lines = [f"{citation.osis}: {citation.snippet}" for citation in answer.citations]
    synthesized_view = "\n".join(synthesis_lines)
    return CollaborationResponse(thread=thread, synthesized_view=synthesized_view, answer=answer)


def build_sermon_prep_package(response: SermonPrepResponse, *, format: str) -> tuple[str, str]:
    manifest = {
        "export_id": f"sermon-{response.answer.citations[0].document_id if response.answer.citations else 'unknown'}",
        "schema_version": "2024-07-01",
        "filters": {"topic": response.topic, "osis": response.osis},
        "git_sha": get_git_sha(),
    }
    if format == "markdown":
        lines = ["---", f"export_id: {manifest['export_id']}", f"schema_version: {manifest['schema_version']}"]
        lines.append(f"filters: {manifest['filters']}")
        lines.append("---\n")
        lines.append(f"# Sermon Prep — {response.topic}")
        if response.osis:
            lines.append(f"Focus Passage: {response.osis}\n")
        lines.append("## Outline")
        for item in response.outline:
            lines.append(f"- {item}")
        lines.append("\n## Key Points")
        for citation in response.answer.citations:
            lines.append(f"- {citation.osis} ({citation.anchor}): {citation.snippet}")
        body = "\n".join(lines)
        return body, "text/markdown"
    if format == "ndjson":
        import json

        lines = [json.dumps(manifest)]
        for citation in response.answer.citations:
            lines.append(
                json.dumps(
                    {
                        "osis": citation.osis,
                        "anchor": citation.anchor,
                        "snippet": citation.snippet,
                        "document_id": citation.document_id,
                    }
                )
            )
        return "\n".join(lines) + "\n", "application/x-ndjson"
    if format == "csv":
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["osis", "anchor", "snippet", "document_id"])
        writer.writeheader()
        for citation in response.answer.citations:
            writer.writerow(
                {
                    "osis": citation.osis,
                    "anchor": citation.anchor,
                    "snippet": citation.snippet,
                    "document_id": citation.document_id,
                }
            )
        body = buffer.getvalue()
        prefix = f"export_id={manifest['export_id']},schema_version={manifest['schema_version']},filters={manifest['filters']},git_sha={manifest['git_sha']}\n"
        return prefix + body, "text/csv"
    raise ValueError(f"Unsupported format: {format}")


def build_transcript_package(
    session: Session,
    document_id: str,
    *,
    format: str,
) -> tuple[str, str]:
    document = session.get(Document, document_id)
    if document is None:
        raise GuardrailError(f"Document {document_id} not found")
    passages = (
        session.query(Passage)
        .filter(Passage.document_id == document_id)
        .order_by(
            Passage.page_no.asc(),
            Passage.t_start.asc(),
            Passage.start_char.asc(),
        )
        .all()
    )
    manifest = {
        "export_id": f"transcript-{document_id}",
        "schema_version": "2024-07-01",
        "filters": {"document_id": document_id},
        "git_sha": get_git_sha(),
    }
    rows = []
    for passage in passages:
        speaker = None
        if passage.meta and isinstance(passage.meta, dict):
            speaker = passage.meta.get("speaker")
        rows.append(
            {
                "speaker": speaker or "Narrator",
                "text": passage.text,
                "osis": passage.osis_ref,
                "t_start": passage.t_start,
                "t_end": passage.t_end,
                "page_no": passage.page_no,
                "passage_id": passage.id,
            }
        )
    if format == "markdown":
        lines = ["---", f"export_id: {manifest['export_id']}", f"schema_version: {manifest['schema_version']}"]
        lines.append(f"filters: {manifest['filters']}")
        lines.append("---\n")
        lines.append(f"# Q&A Transcript — {document.title or document_id}")
        for row in rows:
            anchor = row["osis"] or row["page_no"] or row["t_start"]
            lines.append(f"- **{row['speaker']}** ({anchor}): {row['text']}")
        return "\n".join(lines), "text/markdown"
    if format == "ndjson":
        import json

        lines = [json.dumps(manifest)]
        for row in rows:
            lines.append(json.dumps(row, ensure_ascii=False))
        return "\n".join(lines) + "\n", "application/x-ndjson"
    if format == "csv":
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()) if rows else ["speaker", "text"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        header = f"export_id={manifest['export_id']},schema_version={manifest['schema_version']},filters={manifest['filters']},git_sha={manifest['git_sha']}\n"
        return header + buffer.getvalue(), "text/csv"
    raise ValueError(f"Unsupported format: {format}")


__all__ = [
    "CollaborationResponse",
    "ComparativeAnalysisResponse",
    "CorpusCurationReport",
    "DevotionalResponse",
    "GuardrailError",
    "MultimediaDigestResponse",
    "RAGAnswer",
    "RAGCitation",
    "SermonPrepResponse",
    "VerseCopilotResponse",
    "build_sermon_prep_package",
    "build_transcript_package",
    "generate_comparative_analysis",
    "generate_devotional_flow",
    "generate_multimedia_digest",
    "generate_sermon_prep_outline",
    "generate_verse_brief",
    "run_corpus_curation",
    "run_research_reconciliation",
]
