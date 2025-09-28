"""Digest orchestration helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..analytics.topics import (
    TopicDigest,
    generate_topic_digest,
    load_topic_digest,
    store_topic_digest,
    upsert_digest_document,
)


class DigestService:
    """Coordinate topic digest generation and persistence."""

    def __init__(self, session: Session):
        self._session = session

    def ensure_latest(self) -> TopicDigest | None:
        """Load the cached digest, generating and persisting when missing."""

        digest = load_topic_digest(self._session)
        if digest is None:
            digest = generate_topic_digest(self._session)
            upsert_digest_document(self._session, digest)
            store_topic_digest(self._session, digest)
        return digest

    def refresh(self, hours: int) -> TopicDigest:
        """Force regeneration of the digest for the supplied lookback window."""

        since = datetime.now(UTC) - timedelta(hours=hours)
        digest = generate_topic_digest(self._session, since)
        upsert_digest_document(self._session, digest)
        store_topic_digest(self._session, digest)
        return digest

