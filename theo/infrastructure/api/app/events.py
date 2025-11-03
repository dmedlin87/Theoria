"""Service-level event helpers for API infrastructure."""
from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Mapping

from theo.application.facades.telemetry import log_workflow_event

from .ingest.embeddings import get_embedding_service

logger = logging.getLogger(__name__)


def _normalise_ids(values: Iterable[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return tuple(ordered)


def notify_document_ingested(
    *,
    document_id: str,
    workflow: str,
    passage_ids: Sequence[str] | None = None,
    case_object_ids: Sequence[str] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> None:
    """Perform synchronous side-effects after a document has been stored."""

    try:
        get_embedding_service()
    except Exception:  # pragma: no cover - defensive warmup
        logger.debug("embedding service warmup failed", exc_info=True)

    log_workflow_event(
        "ingest.document.persisted",
        workflow=workflow,
        document_id=document_id,
        passage_count=len(tuple(passage_ids or ())),
        case_object_count=len(tuple(case_object_ids or ())),
        metadata=dict(metadata) if metadata else None,
    )


def notify_case_objects_upserted(
    ids: Sequence[str], *, document_id: str | None = None
) -> None:
    """Dispatch case object updates to the worker queue when available."""

    ordered = _normalise_ids(ids)
    if not ordered:
        return

    try:
        from .workers import tasks as worker_tasks
    except Exception:  # pragma: no cover - optional worker wiring
        logger.debug("case object worker tasks unavailable", exc_info=True)
        return

    handler = getattr(worker_tasks, "on_case_object_upsert", None)
    if handler is None:
        logger.debug("case object upsert handler missing")
        return

    for case_object_id in ordered:
        try:
            maybe_delay = getattr(handler, "delay", None)
            if callable(maybe_delay):
                maybe_delay(case_object_id, document_id=document_id)
            else:
                handler(case_object_id, document_id=document_id)
        except TypeError:
            # Maintain backwards compatibility with handlers that only accept
            # the identifier argument.
            try:
                maybe_delay = getattr(handler, "delay", None)
                if callable(maybe_delay):
                    maybe_delay(case_object_id)
                else:
                    handler(case_object_id)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception(
                    "case object handler failed",
                    extra={"case_object_id": case_object_id},
                )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "case object handler failed",
                extra={"case_object_id": case_object_id},
            )


__all__ = [
    "notify_case_objects_upserted",
    "notify_document_ingested",
]

