"""Ingestion service encapsulating pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from fastapi import Depends
from sqlalchemy.orm import Session

from ..core.settings import Settings, get_settings
from ..ingest.pipeline import (
    run_pipeline_for_file,
    run_pipeline_for_transcript,
    run_pipeline_for_url,
)
from ..models.documents import SimpleIngestRequest
from ..telemetry import log_workflow_event
from theo.services.cli import ingest_folder as cli_ingest

DocumentLike = Any


@dataclass
class IngestionService:
    """Coordinate ingestion workflows for API endpoints."""

    settings: Settings
    run_file_pipeline: Callable[[Session, Path, dict[str, Any] | None], DocumentLike]
    run_url_pipeline: Callable[..., DocumentLike]
    run_transcript_pipeline: Callable[..., DocumentLike]
    cli_module: Any
    log_workflow: Callable[..., None]

    def ingest_file(
        self,
        session: Session,
        source_path: Path,
        frontmatter: dict[str, Any] | None,
    ) -> DocumentLike:
        """Persist *source_path* via the file ingestion pipeline."""

        return self.run_file_pipeline(session, source_path, frontmatter)

    def ingest_url(
        self,
        session: Session,
        url: str,
        *,
        source_type: str | None = None,
        frontmatter: dict[str, Any] | None = None,
    ) -> DocumentLike:
        """Persist *url* via the URL ingestion pipeline."""

        return self.run_url_pipeline(
            session,
            url,
            source_type=source_type,
            frontmatter=frontmatter,
        )

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

        return self.run_transcript_pipeline(
            session,
            transcript_path,
            frontmatter=frontmatter,
            audio_path=audio_path,
            transcript_filename=transcript_filename,
            audio_filename=audio_filename,
        )

    def stream_simple_ingest(
        self, payload: SimpleIngestRequest
    ) -> Iterator[dict[str, Any]]:
        """Yield ingestion events for the CLI-compatible simple ingest endpoint."""

        allowlist: Sequence[str] | None = getattr(
            self.settings, "simple_ingest_allowed_roots", None
        )
        items = self.cli_module._discover_items(payload.sources, allowlist)
        overrides = self.cli_module._apply_default_metadata(payload.metadata or {})
        post_batch_steps = self.cli_module._parse_post_batch_steps(
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
            batches = self.cli_module._batched(items, payload.batch_size)
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
                    document_ids = self.cli_module._ingest_batch_via_api(
                        batch, overrides, post_batch_steps
                    )
                    for item, doc_id in zip(batch, document_ids):
                        processed += 1
                        yield {
                            "event": "processed",
                            "target": item.label,
                            "document_id": doc_id,
                        }
                else:
                    if post_batch_steps:
                        yield {
                            "event": "warning",
                            "message": (
                                "Post-batch steps require API mode; skipping."
                            ),
                        }
                    task_ids = self.cli_module._queue_batch_via_worker(
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

    return IngestionService(
        settings=settings,
        run_file_pipeline=run_pipeline_for_file,
        run_url_pipeline=run_pipeline_for_url,
        run_transcript_pipeline=run_pipeline_for_transcript,
        cli_module=cli_ingest,
        log_workflow=log_workflow_event,
    )
