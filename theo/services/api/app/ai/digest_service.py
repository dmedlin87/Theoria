"""Digest orchestration helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..analytics.topics import TopicDigest, load_topic_digest


class DigestService:
    """Coordinate topic digest generation and persistence."""

    def __init__(self, session: Session, *, ttl: timedelta):
        self._session = session
        self._ttl = ttl

    def ensure_latest(self) -> TopicDigest | None:
        """Load the cached digest, generating and persisting when missing or stale."""

        digest = load_topic_digest(self._session)
        if digest is None or self._is_expired(digest):
            from ..routes import ai as ai_module

            digest = ai_module.generate_topic_digest(self._session)
            ai_module.upsert_digest_document(self._session, digest)
            ai_module.store_topic_digest(self._session, digest)
        return digest

    def _is_expired(self, digest: TopicDigest) -> bool:
        expires_at = digest.generated_at + self._ttl
        return expires_at <= datetime.now(UTC)

    def refresh(self, hours: int) -> TopicDigest:
        """Force regeneration of the digest for the supplied lookback window."""

        since = datetime.now(UTC) - timedelta(hours=hours)
        from ..routes import ai as ai_module

        digest = ai_module.generate_topic_digest(self._session, since)
        ai_module.upsert_digest_document(self._session, digest)
        ai_module.store_topic_digest(self._session, digest)
        return digest

