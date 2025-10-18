"""Topic monitoring utilities."""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.application.facades.events import get_event_publisher
from theo.application.ports.events import DomainEvent, EventDispatchError
from theo.application.facades.settings_store import load_setting, save_setting
from theo.services.api.app.persistence_models import Document
from ..models.base import APIModel
from .openalex import OpenAlexClient

SETTINGS_KEY = "topic-digest"


LOGGER = logging.getLogger(__name__)


def _extract_topics(document: Document) -> list[str]:
    topics: list[str] = []
    if document.bib_json and isinstance(document.bib_json, dict):
        primary = document.bib_json.get("primary_topic")
        if isinstance(primary, str):
            topics.append(primary)
        bib_topics = document.bib_json.get("topics")
        if isinstance(bib_topics, list):
            topics.extend(str(item) for item in bib_topics)
    if document.topics:
        if isinstance(document.topics, list):
            topics.extend(str(item) for item in document.topics)
        elif isinstance(document.topics, dict):
            topics.extend(str(value) for value in document.topics.values())
    unique_topics: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        if topic and topic not in seen:
            seen.add(topic)
            unique_topics.append(topic)
    return unique_topics


class TopicCluster(APIModel):
    topic: str
    new_documents: int
    total_documents: int
    document_ids: list[str]


class TopicDigest(APIModel):
    generated_at: datetime
    window_start: datetime
    topics: list[TopicCluster]


def _historical_counts(session: Session) -> Counter:
    counts: Counter[str] = Counter()
    rows = session.execute(
        select(Document.id, Document.bib_json, Document.topics)
    ).all()
    for _id, bib_json, topics in rows:
        doc = Document(id=_id)
        doc.bib_json = bib_json
        doc.topics = topics
        for topic in _extract_topics(doc):
            counts[topic] += 1
    return counts


def _attach_topics(document: Document, topics: list[str]) -> bool:
    """Persist unique topics on the document and bib metadata."""

    if not topics:
        return False

    existing = _extract_topics(document)
    additions = [topic for topic in topics if topic and topic not in existing]
    if not additions:
        return False

    merged = existing + additions
    document.topics = merged

    if isinstance(document.bib_json, dict):
        updated_bib = dict(document.bib_json)
    else:
        updated_bib = {}

    bib_topics = updated_bib.get("topics")
    if isinstance(bib_topics, list):
        deduped = []
        seen: set[str] = set()
        for value in list(bib_topics) + additions:
            if value and value not in seen:
                seen.add(value)
                deduped.append(value)
        updated_bib["topics"] = deduped
    else:
        updated_bib["topics"] = additions

    document.bib_json = updated_bib or None
    return True


def generate_topic_digest(
    session: Session,
    since: datetime | None = None,
    *,
    openalex_client: OpenAlexClient | None = None,
) -> TopicDigest:
    if since is None:
        since = datetime.now(UTC) - timedelta(days=7)
    rows = (
        session.execute(select(Document).where(Document.created_at >= since))
        .scalars()
        .all()
    )

    updated = False
    with ExitStack() as stack:
        client = openalex_client
        if client is None:
            client = OpenAlexClient()
            stack.callback(client.close)

        for document in rows:
            existing_topics = _extract_topics(document)
            if existing_topics:
                continue
            if not document.doi:
                continue
            topics = client.fetch_topics(document.doi, document.title)
            if _attach_topics(document, topics):
                session.add(document)
                updated = True

        if updated:
            session.flush()
    topic_documents: dict[str, set[str]] = defaultdict(set)
    for document in rows:
        for topic in _extract_topics(document):
            topic_documents[topic].add(document.id)

    if not topic_documents:
        return TopicDigest(
            generated_at=datetime.now(UTC), window_start=since, topics=[]
        )

    historical = _historical_counts(session)
    clusters = []
    for topic, ids in sorted(
        topic_documents.items(), key=lambda item: (-len(item[1]), item[0])
    ):
        doc_ids = sorted(ids)
        total = historical.get(topic, 0)
        clusters.append(
            TopicCluster(
                topic=topic,
                new_documents=len(doc_ids),
                total_documents=total,
                document_ids=doc_ids,
            )
        )

    return TopicDigest(
        generated_at=datetime.now(UTC), window_start=since, topics=clusters
    )


def store_topic_digest(session: Session, digest: TopicDigest) -> None:
    save_setting(session, SETTINGS_KEY, digest.model_dump(mode="json"))
    publisher = get_event_publisher()
    event = DomainEvent(
        type="theo.topic_digest.generated",
        payload={
            "digest": digest.model_dump(mode="json"),
            "topic_count": len(digest.topics),
        },
        metadata={
            "generated_at": digest.generated_at,
            "window_start": digest.window_start,
        },
    )
    try:
        publisher.publish(event)
    except EventDispatchError as exc:
        LOGGER.warning("Digest event delivery reported failures: %s", exc)
    except Exception:  # pragma: no cover - defensive guard for unexpected failures
        LOGGER.exception("Unexpected error while publishing topic digest event")


def load_topic_digest(session: Session) -> TopicDigest | None:
    payload = load_setting(session, SETTINGS_KEY)
    if not payload:
        return None
    return TopicDigest.model_validate(payload)


def upsert_digest_document(session: Session, digest: TopicDigest) -> Document:
    """Create or update a document representation for the supplied digest."""

    summary_lines = [
        f"Topic digest generated at {digest.generated_at.isoformat()} for window starting {digest.window_start.isoformat()}."
    ]
    clusters: list[dict[str, Any]] = []
    for cluster in digest.topics:
        clusters.append(
            {
                "topic": cluster.topic,
                "new_documents": cluster.new_documents,
                "total_documents": cluster.total_documents,
                "document_ids": cluster.document_ids,
            }
        )
        summary_lines.append(
            f"- {cluster.topic}: {cluster.new_documents} new / {cluster.total_documents} total"
        )
        if cluster.document_ids:
            summary_lines.append(f"  Documents: {', '.join(cluster.document_ids)}")

    if not digest.topics:
        summary_lines.append(
            "No new topical activity detected for the selected window."
        )

    metadata = {
        "type": "topic_digest",
        "generated_at": digest.generated_at.isoformat(),
        "window_start": digest.window_start.isoformat(),
        "clusters": clusters,
    }

    document = (
        session.query(Document)
        .filter(Document.source_type == "digest")
        .order_by(Document.created_at.desc())
        .first()
    )

    title = (
        f"Topic Digest ({digest.window_start.date()} – {digest.generated_at.date()})"
    )
    topics = [cluster.topic for cluster in digest.topics]
    abstract = "\n".join(summary_lines)

    if document is None:
        document = Document(
            title=title,
            source_type="digest",
            collection="Digests",
            abstract=abstract,
            topics=topics,
            bib_json=metadata,
        )
    else:
        document.title = title
        document.collection = document.collection or "Digests"
        document.abstract = abstract
        document.topics = topics or None
        document.bib_json = metadata

    session.add(document)
    session.flush()
    return document


__all__ = [
    "TopicCluster",
    "TopicDigest",
    "generate_topic_digest",
    "store_topic_digest",
    "load_topic_digest",
    "upsert_digest_document",
]
