"""Batch post-ingest intelligence CLI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Iterable

import click
from sqlalchemy.orm import Session

from ..api.app.analytics.topics import (
    generate_topic_digest,
    store_topic_digest,
    upsert_digest_document,
)
from theo.adapters.persistence.models import Document, Passage
from theo.infrastructure.api.app.ai.rag.corpus import run_corpus_curation
from theo.application.services.bootstrap import resolve_application


APPLICATION_CONTAINER, _ADAPTER_REGISTRY = resolve_application()


def get_engine():  # pragma: no cover - transitional wiring helper
    return _ADAPTER_REGISTRY.resolve("engine")


def _recent_documents(session: Session, since: datetime) -> Iterable[Document]:
    return (
        session.query(Document)
        .filter(Document.created_at >= since)
        .order_by(Document.created_at.asc())
        .all()
    )


def _summarise_document(session: Session, document: Document) -> tuple[str, list[str]]:
    passages = (
        session.query(Passage)
        .filter(Passage.document_id == document.id)
        .order_by(
            Passage.page_no.asc(), Passage.t_start.asc(), Passage.start_char.asc()
        )
        .limit(3)
        .all()
    )
    text = " ".join(passage.text for passage in passages) or (document.abstract or "")
    summary = (text[:380] + "…") if len(text) > 380 else text
    tags: list[str] = []
    if document.bib_json and isinstance(document.bib_json, dict):
        primary = document.bib_json.get("primary_topic")
        if isinstance(primary, str):
            tags.append(primary)
        extra = document.bib_json.get("topics")
        if isinstance(extra, list):
            tags.extend(str(item) for item in extra[:3])
    return summary, tags


def _persist_summary(
    session: Session, document: Document, summary: str, tags: list[str]
) -> Document:
    ai_doc = Document(
        title=f"AI Summary · {document.title or document.id}",
        authors=document.authors,
        collection=document.collection,
        source_type="ai_summary",
        abstract=summary,
        bib_json={
            "generated_from": document.id,
            "tags": tags,
            "primary_topic": tags[0] if tags else None,
        },
    )
    session.add(ai_doc)
    session.commit()
    return ai_doc


@click.command()
@click.option(
    "--hours", type=int, default=24, show_default=True, help="Look back window in hours"
)
@click.option("--dry-run", is_flag=True, help="Print work without persisting summaries")
def main(hours: int, dry_run: bool) -> None:
    """Generate summaries/tags for freshly ingested documents."""

    since = datetime.now(UTC) - timedelta(hours=hours)
    engine = get_engine()
    with Session(engine) as session:
        click.echo(f"Scanning documents since {since.isoformat()}...")
        documents = _recent_documents(session, since)
        if not documents:
            click.echo("No documents found in the given window.")
            return

        report = run_corpus_curation(session, since=since)
        click.echo(f"Identified {report.documents_processed} documents.")
        for line in report.summaries:
            click.echo(f" - {line}")

        for document in documents:
            summary, tags = _summarise_document(session, document)
            click.echo(
                f"Summarising {document.title or document.id} → tags: {', '.join(tags) or 'n/a'}"
            )
            if dry_run:
                continue
            ai_doc = _persist_summary(session, document, summary, tags)
            click.echo(f"  Saved ai_summary document {ai_doc.id}")

        click.echo("Generating weekly topic digest…")
        digest = generate_topic_digest(session)
        if dry_run:
            click.echo(
                f"Digest preview contains {len(digest.topics)} clusters since {digest.window_start.date()}"
            )
            return

        digest_document = upsert_digest_document(session, digest)
        session.commit()
        store_topic_digest(session, digest)
        click.echo(
            f"Updated digest document {digest_document.id} covering {len(digest.topics)} clusters"
        )


if __name__ == "__main__":
    main()
