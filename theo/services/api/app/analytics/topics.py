"""Topic monitoring utilities."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.settings_store import load_setting, save_setting
from ..db.models import Document
from ..models.base import APIModel

SETTINGS_KEY = "topic-digest"


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
    return [topic for topic in topics if topic]


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


def generate_topic_digest(
    session: Session, since: datetime | None = None
) -> TopicDigest:
    if since is None:
        since = datetime.now(UTC) - timedelta(days=7)
    rows = (
        session.execute(select(Document).where(Document.created_at >= since))
        .scalars()
        .all()
    )
    topic_documents: dict[str, list[str]] = defaultdict(list)
    for document in rows:
        for topic in _extract_topics(document):
            topic_documents[topic].append(document.id)

    if not topic_documents:
        return TopicDigest(
            generated_at=datetime.now(UTC), window_start=since, topics=[]
        )

    historical = _historical_counts(session)
    clusters = []
    for topic, ids in sorted(
        topic_documents.items(), key=lambda item: (-len(item[1]), item[0])
    ):
        total = historical.get(topic, 0)
        clusters.append(
            TopicCluster(
                topic=topic,
                new_documents=len(ids),
                total_documents=total,
                document_ids=ids,
            )
        )

    return TopicDigest(
        generated_at=datetime.now(UTC), window_start=since, topics=clusters
    )


def store_topic_digest(session: Session, digest: TopicDigest) -> None:
    save_setting(session, SETTINGS_KEY, digest.model_dump(mode="json"))


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
