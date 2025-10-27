"""Helpers for persisting and managing AI workflow audit logs."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Mapping, Sequence

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SASession, sessionmaker

from theo.infrastructure.api.app.persistence_models import AuditLog

LOGGER = logging.getLogger(__name__)


def _default_json_encoder(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    return str(value)


def _serialise_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json", exclude_none=True)
        except TypeError:
            return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value):
        return {
            field.name: _serialise_payload(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {
            key: _serialise_payload(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_serialise_payload(item) for item in value]
    return value


def compute_prompt_hash(
    text: str | None = None, payload: Mapping[str, Any] | None = None
) -> str:
    if text:
        candidate = text.strip()
        if candidate:
            return hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    if payload is not None:
        serialised = _serialise_payload(payload)
        try:
            encoded = json.dumps(
                serialised, sort_keys=True, ensure_ascii=False, default=_default_json_encoder
            )
        except TypeError:
            encoded = json.dumps(
                _serialise_payload(serialised),
                sort_keys=True,
                ensure_ascii=False,
                default=_default_json_encoder,
            )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return hashlib.sha256(b"").hexdigest()


def serialise_citations(citations: Sequence[Any] | None) -> list[Any]:
    if not citations:
        return []
    payload = _serialise_payload(list(citations))
    return payload if isinstance(payload, list) else []


def serialise_claim_cards(claim_cards: Sequence[Any] | None) -> list[Any]:
    if not claim_cards:
        return []
    payload = _serialise_payload(list(claim_cards))
    return payload if isinstance(payload, list) else []


class AuditLogWriter:
    """Persist audit log entries without impacting the caller transaction."""

    def __init__(self, session_factory: sessionmaker[SASession] | None) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_session(cls, session: SASession | object) -> "AuditLogWriter":
        try:
            bind = session.get_bind()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - defensive fallback for stub sessions
            LOGGER.debug("Audit logging disabled: session is not database-backed", exc_info=True)
            return cls(None)
        if bind is None:
            return cls(None)
        # Use SQLAlchemy's base ``Session`` class for audit logging rather than
        # reusing the application's custom subclass.  The application session
        # adds aggressive SQLite handle cleanup in ``close`` which interferes
        # with other concurrently active sessions (for example, the request
        # session responsible for the guardrail workflow).  When audit logging
        # fails to commit—common under SQLite when another transaction is
        # writing—the cleanup routine could close the primary connection and
        # leave the request transaction in a broken state.  Sticking with the
        # stock ``Session`` avoids that cross-session interference while still
        # providing the isolation audit logging needs.
        factory = sessionmaker(
            bind=bind,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
            class_=SASession,
        )
        return cls(factory)

    def log(
        self,
        *,
        workflow: str,
        prompt_hash: str,
        model_preset: str | None,
        inputs: Mapping[str, Any] | Sequence[Any] | None,
        outputs: Mapping[str, Any] | Sequence[Any] | None = None,
        citations: Sequence[Any] | None = None,
        claim_cards: Sequence[Any] | None = None,
        audit_metadata: Mapping[str, Any] | Sequence[Any] | None = None,
        status: str = "generated",
    ) -> None:
        if self._session_factory is None:
            return None
        record = AuditLog(
            workflow=workflow,
            status=status,
            prompt_hash=prompt_hash,
            model_preset=model_preset,
            inputs=_serialise_payload(inputs or {}),
            outputs=_serialise_payload(outputs) if outputs is not None else None,
            citations=serialise_citations(citations),
            claim_cards=serialise_claim_cards(claim_cards),
            audit_metadata=_serialise_payload(audit_metadata)
            if audit_metadata is not None
            else None,
        )
        session = self._session_factory()
        try:
            session.add(record)
            session.commit()
        except SQLAlchemyError:  # pragma: no cover - defensive persistence guard
            session.rollback()
            LOGGER.warning("Unable to persist audit log entry", exc_info=True)
        except Exception:  # pragma: no cover - defensive catch-all
            session.rollback()
            LOGGER.warning("Unexpected failure while persisting audit log", exc_info=True)
        finally:
            session.close()


def fetch_recent_audit_logs(
    session: SASession, *, limit: int = 100, workflow: str | None = None
) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if workflow:
        query = query.where(AuditLog.workflow == workflow)
    if limit is not None and limit > 0:
        query = query.limit(limit)
    return list(session.execute(query).scalars())


def purge_audit_logs(
    session: SASession,
    *,
    older_than: datetime | None = None,
    keep_latest: int | None = None,
) -> int:
    # Build a subquery to select IDs to delete
    ids_subq = None
    if keep_latest is not None and keep_latest > 0:
        # Select all IDs ordered by created_at DESC, skip the most recent `keep_latest`
        ids_subq = (
            select(AuditLog.id)
            .order_by(AuditLog.created_at.desc())
            .offset(keep_latest)
        )
        if older_than is not None:
            ids_subq = ids_subq.where(AuditLog.created_at < older_than)
    elif older_than is not None:
        # Only filter by older_than
        ids_subq = select(AuditLog.id).where(AuditLog.created_at < older_than)
    else:
        # Nothing to delete
        return 0

    # Use the subquery in the delete statement
    result = session.execute(
        delete(AuditLog).where(AuditLog.id.in_(ids_subq))
    )
    session.commit()
    return result.rowcount or 0


__all__ = [
    "AuditLogWriter",
    "compute_prompt_hash",
    "fetch_recent_audit_logs",
    "purge_audit_logs",
    "serialise_citations",
    "serialise_claim_cards",
]
