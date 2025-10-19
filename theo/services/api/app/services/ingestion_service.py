"""Ingestion service encapsulating pipeline orchestration."""

from __future__ import annotations

import importlib
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterator, Sequence

from fastapi import Depends, status
from sqlalchemy.orm import Session

from theo.application.facades.events import get_event_publisher
from theo.application.ports.events import (
    DomainEvent,
    EventDispatchError,
    EventPublisher,
    NullEventPublisher,
)
from theo.application.facades.settings import Settings, get_settings
from ..ingest.pipeline import (
    PipelineDependencies,
    run_pipeline_for_file,
    run_pipeline_for_transcript,
    run_pipeline_for_url,
)
from ..models.documents import SimpleIngestRequest
from ..telemetry import log_workflow_event
from ..errors import IngestionError, Severity
from ..utils.imports import LazyImportModule


cli_ingest = LazyImportModule("theo.services.cli.ingest_folder")

DocumentLike = Any

_BASE_RUN_PIPELINE_FOR_FILE = run_pipeline_for_file
_BASE_RUN_PIPELINE_FOR_URL = run_pipeline_for_url
_BASE_RUN_PIPELINE_FOR_TRANSCRIPT = run_pipeline_for_transcript

_CLI_INGEST_MODULE: ModuleType | None = None


LOGGER = logging.getLogger(__name__)


def _load_cli_ingest_module() -> ModuleType:
    """Import the CLI ingest module lazily to avoid circular imports."""

    global _CLI_INGEST_MODULE

    if _CLI_INGEST_MODULE is not None:
        return _CLI_INGEST_MODULE

    module = importlib.import_module("theo.services.cli.ingest_folder")
    _CLI_INGEST_MODULE = module
    return module


@dataclass
class IngestionService:
    """Coordinate ingestion workflows for API endpoints."""

    settings: Settings
    run_file_pipeline: Callable[..., DocumentLike]
    run_url_pipeline: Callable[..., DocumentLike]
    run_transcript_pipeline: Callable[..., DocumentLike]
    cli_module: Any
    log_workflow: Callable[..., None]
    event_publisher: EventPublisher = field(default_factory=NullEventPublisher)

    def _get_cli_module(self) -> Any:
        module = self.cli_module
        loader = getattr(module, "load", None)
        if callable(loader):
            module = loader()
        return module

    def _snapshot_document(self, document: Any) -> dict[str, Any]:
        fields = (
            "id",
            "title",
            "source_type",
            "source_url",
            "collection",
            "sha256",
            "created_at",
            "updated_at",
        )
        snapshot: dict[str, Any] = {}
        for name in fields:
            value = getattr(document, name, None)
            if value is not None:
                snapshot[name] = value
        return snapshot

    def _publish_ingestion_event(
        self,
        document: Any,
        *,
        source: dict[str, Any],
        frontmatter: dict[str, Any] | None,
    ) -> None:
        document_id = getattr(document, "id", None)
        payload: dict[str, Any] = {
            "document": self._snapshot_document(document),
            "source": {key: value for key, value in source.items() if value is not None},
        }
        if frontmatter:
            payload["frontmatter"] = frontmatter

        event = DomainEvent(
            type="theo.ingestion.completed",
            payload=payload,
            key=str(document_id) if document_id is not None else None,
            metadata={"source_kind": source.get("kind")},
        )
        try:
            self.event_publisher.publish(event)
        except EventDispatchError as exc:
            LOGGER.warning(
                "One or more event sinks failed while publishing ingestion event for %s: %s",
                document_id or "<unknown>",
                exc,
            )
        except Exception:  # pragma: no cover - defensive guard for unexpected failures
            LOGGER.exception(
                "Unexpected error while publishing ingestion event for %s",
                document_id or "<unknown>",
            )

    def ingest_file(
        self,
        session: Session,
        source_path: Path,
        frontmatter: dict[str, Any] | None,
    ) -> DocumentLike:
        """Persist *source_path* via the file ingestion pipeline."""

        document = self.run_file_pipeline(
            session,
            source_path,
            frontmatter,
            dependencies=PipelineDependencies(settings=self.settings),
        )
        self._publish_ingestion_event(
            document,
            source={"kind": "file", "path": str(source_path)},
            frontmatter=frontmatter,
        )
        return document

    def ingest_url(
        self,
        session: Session,
        url: str,
        *,
        source_type: str | None = None,
        frontmatter: dict[str, Any] | None = None,
    ) -> DocumentLike:
        """Persist *url* via the URL ingestion pipeline."""

        document = self.run_url_pipeline(
            session,
            url,
            source_type=source_type,
            frontmatter=frontmatter,
            dependencies=PipelineDependencies(settings=self.settings),
        )
        self._publish_ingestion_event(
            document,
            source={
                "kind": "url",
                "url": url,
                "requested_source_type": source_type,
            },
            frontmatter=frontmatter,
        )
        return document

    def ingest_transcript(
        self,
        session: Session,
        transcript_path: Path,
        *,
        frontmatter: dict[str, Any] | None = None,
        audio_path: Path | None = None,
        transcript_filename: str | None = None,
        audio_filename: str | None = None,
    ) -> DocumentLike:
        """Persist transcript and optional audio artefacts."""

        document = self.run_transcript_pipeline(
            session,
            transcript_path,
            frontmatter=frontmatter,
            audio_path=audio_path,
            transcript_filename=transcript_filename,
            audio_filename=audio_filename,
            dependencies=PipelineDependencies(settings=self.settings),
        )
        self._publish_ingestion_event(
            document,
            source={
                "kind": "transcript",
                "transcript_path": str(transcript_path),
                "audio_path": str(audio_path) if audio_path else None,
            },
            frontmatter=frontmatter,
        )
        return document

    def stream_simple_ingest(
        self, payload: SimpleIngestRequest
    ) -> Iterator[dict[str, Any]]:
        """Yield ingestion events for the CLI-compatible simple ingest endpoint."""

        allowlist: Sequence[Path] | Sequence[str] | None = getattr(
            self.settings, "simple_ingest_allowed_roots", None
        )

        cli_module = self._get_cli_module()

        if not allowlist:
            finder = getattr(cli_module, "find_local_sources", None)
            if finder is not None:
                local_sources = finder(payload.sources)
            else:  # pragma: no cover - compatibility shim for older CLI modules
                local_sources = [
                    source.strip()
                    for source in payload.sources
                    if source.strip()
                    and not self.cli_module._looks_like_url(source.strip())
                ]

            if local_sources:
                raise IngestionError(
                    "Local ingestion is disabled until allowlisted roots are configured.",
                    code="INGESTION_LOCAL_SOURCES_DISABLED",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    severity=Severity.USER,
                    hint="Set simple_ingest_allowed_roots to permit filesystem ingestion.",
                    data={"sources": local_sources},
                )

        items = cli_module._discover_items(payload.sources, allowlist)
        overrides = cli_module._apply_default_metadata(payload.metadata or {})
        post_batch_steps = cli_module._parse_post_batch_steps(
            tuple(payload.post_batch or ())
        )
        mode = payload.mode.lower()

        total = len(items)
        self.log_workflow(
            "api.simple_ingest.started",
            workflow="api.simple_ingest",
            total=total,
            mode=mode,
            dry_run=payload.dry_run,
        )
        yield {
            "event": "start",
            "total": total,
            "mode": mode,
            "dry_run": payload.dry_run,
            "batch_size": payload.batch_size,
        }

        if not items:
            self.log_workflow(
                "api.simple_ingest.empty",
                workflow="api.simple_ingest",
                mode=mode,
            )
            yield {"event": "empty"}
            return

        for item in items:
            yield {
                "event": "discovered",
                "target": item.label,
                "source_type": item.source_type,
                "remote": item.is_remote,
            }

        processed = 0
        queued = 0

        try:
            batches = cli_module._batched(items, payload.batch_size)
            for batch_number, batch in enumerate(batches, start=1):
                yield {
                    "event": "batch",
                    "number": batch_number,
                    "size": len(batch),
                    "mode": mode,
                }

                if payload.dry_run:
                    for item in batch:
                        yield {
                            "event": "dry-run",
                            "target": item.label,
                            "source_type": item.source_type,
                        }
                    continue

                if mode == "api":
                    outcomes = cli_module._ingest_batch_via_api(
                        batch,
                        overrides,
                        post_batch_steps,
                        dependencies=PipelineDependencies(settings=self.settings),
                        skip_unchanged_enrichment=payload.skip_unchanged_enrichment,
                    )
                    for item, outcome in zip(batch, outcomes):
                        processed += 1
                        yield {
                            "event": "processed",
                            "target": item.label,
                            "document_id": outcome.document_id,
                            "cache_status": outcome.cache_status,
                        }
                else:
                    if post_batch_steps:
                        yield {
                            "event": "warning",
                            "message": (
                                "Post-batch steps require API mode; skipping."
                            ),
                        }
                    task_ids = cli_module._queue_batch_via_worker(
                        batch, overrides
                    )
                    for item, task_id in zip(batch, task_ids):
                        queued += 1
                        yield {
                            "event": "queued",
                            "target": item.label,
                            "task_id": task_id,
                        }
        except Exception as exc:  # pragma: no cover - defensive guard
            self.log_workflow(
                "api.simple_ingest.failed",
                workflow="api.simple_ingest",
                mode=mode,
                dry_run=payload.dry_run,
                error=str(exc),
            )
            yield {"event": "error", "message": str(exc)}
            return

        self.log_workflow(
            "api.simple_ingest.completed",
            workflow="api.simple_ingest",
            mode=mode,
            dry_run=payload.dry_run,
            processed=processed,
            queued=queued,
            total=total,
        )
        yield {
            "event": "complete",
            "processed": processed,
            "queued": queued,
            "total": total,
            "mode": mode,
        }


def get_ingestion_service(
    settings: Settings = Depends(get_settings),
) -> IngestionService:
    """Dependency factory for :class:`IngestionService`."""

    ingest_module = sys.modules.get("theo.services.api.app.routes.ingest")

    def _resolve_hook(name: str, base_default):
        module_value = getattr(sys.modules[__name__], name, None)
        route_value = getattr(ingest_module, name, None) if ingest_module else None

        if module_value is not None and module_value is not base_default:
            return module_value
        if route_value is not None and route_value is not base_default:
            return route_value
        if module_value is not None:
            return module_value
        if route_value is not None:
            return route_value
        return base_default

    run_file = _resolve_hook("run_pipeline_for_file", _BASE_RUN_PIPELINE_FOR_FILE)
    run_url = _resolve_hook("run_pipeline_for_url", _BASE_RUN_PIPELINE_FOR_URL)
    run_transcript = _resolve_hook(
        "run_pipeline_for_transcript", _BASE_RUN_PIPELINE_FOR_TRANSCRIPT
    )

    cli_source = cli_ingest
    if ingest_module is not None:
        route_cli = getattr(ingest_module, "cli_ingest", None)
        if route_cli is not None:
            cli_source = route_cli

    return IngestionService(
        settings=settings,
        run_file_pipeline=run_file,
        run_url_pipeline=run_url,
        run_transcript_pipeline=run_transcript,
        cli_module=cli_source,
        log_workflow=log_workflow_event,
        event_publisher=get_event_publisher(),
    )


def __getattr__(name: str) -> Any:
    """Provide lazy access to the CLI ingest module for test hooks."""

    if name == "cli_ingest":
        module = _load_cli_ingest_module()
        globals()[name] = module
        return module
    raise AttributeError(name)
