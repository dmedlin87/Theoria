"""Embedding rebuild CLI command implementation."""

from __future__ import annotations

import itertools
import json
import logging
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

import click
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from theo.application.embeddings import (
    EmbeddingRebuildError,
    EmbeddingRebuildOptions,
    EmbeddingRebuildProgress,
    EmbeddingRebuildResult,
    EmbeddingRebuildService,
    EmbeddingRebuildStart,
)
from theo.application.facades.telemetry import (
    get_telemetry_provider,
    instrument_workflow,
    log_workflow_event,
    record_counter,
    record_histogram,
    set_span_attribute,
    set_telemetry_provider,
)
from theo.application.telemetry import (
    EMBEDDING_REBUILD_BATCH_LATENCY_METRIC,
    EMBEDDING_REBUILD_COMMIT_LATENCY_METRIC,
    EMBEDDING_REBUILD_PROGRESS_METRIC,
)
from theo.adapters.persistence.models import Document, Passage
from theo.application.embeddings.checkpoint_store import (
    CheckpointError,
    EmbeddingCheckpoint,
    load_checkpoint,
    save_checkpoint,
)
from theo.infrastructure.api.app.ingest.embeddings import (
    clear_embedding_cache,
    get_embedding_service,
)
from theo.application.services.bootstrap import resolve_application
from theo.domain.services.embeddings import (
    EmbeddingRebuildConfig,
    EmbeddingRebuildInstrumentation,
)

__all__ = ["register_commands", "rebuild_embeddings_cmd"]


_LOGGER = logging.getLogger(__name__)


_BatchItem = TypeVar("_BatchItem")


def _batched(iterable: Iterable[_BatchItem], size: int) -> Iterator[list[_BatchItem]]:
    """Yield successive batches from *iterable* of at most *size* items."""

    if size <= 0:
        raise ValueError("size must be positive")

    batch: list[_BatchItem] = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _normalise_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _load_ids(path: Path) -> list[str]:
    ids = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    ids = [item for item in ids if item]
    # Preserve ordering while removing duplicates
    seen: set[str] = set()
    deduped: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _write_checkpoint(
    path: Path,
    *,
    processed: int,
    total: int,
    last_id: str | None,
    metadata: dict[str, object],
    previous: EmbeddingCheckpoint | None = None,
) -> EmbeddingCheckpoint:
    checkpoint = EmbeddingCheckpoint.build(
        processed=processed,
        total=total,
        last_id=last_id,
        metadata=metadata,
        previous=previous,
    )
    save_checkpoint(path, checkpoint)
    return checkpoint


_TELEMETRY_READY = False


def _ensure_cli_telemetry() -> None:
    """Ensure the CLI has a telemetry provider for instrumentation."""

    global _TELEMETRY_READY
    if _TELEMETRY_READY:
        return

    try:
        get_telemetry_provider()
    except RuntimeError:
        try:
            from theo.infrastructure.api.app.adapters.telemetry import (
                ApiTelemetryProvider,
            )
        except ModuleNotFoundError:  # pragma: no cover - optional dependency missing
            _TELEMETRY_READY = True
            return
        except Exception:  # pragma: no cover - defensive import guard
            _TELEMETRY_READY = True
            return
        try:
            set_telemetry_provider(ApiTelemetryProvider())
        except Exception:  # pragma: no cover - optional dependency safety
            _TELEMETRY_READY = True
            return

    _TELEMETRY_READY = True


def _execute_with_retry(
    session: Session, stmt, *, max_attempts: int = 3, backoff: float = 0.5
) -> any:
    """Execute a database statement with retry logic for transient failures."""
    for attempt in range(1, max_attempts + 1):
        try:
            return session.execute(stmt)
        except SQLAlchemyError as exc:
            _LOGGER.warning(
                "Database query failed on attempt %d/%d: %s",
                attempt, max_attempts, exc
            )
            try:
                session.rollback()
            except SQLAlchemyError as rollback_exc:  # pragma: no cover - defensive
                _LOGGER.error(
                    "Failed to rollback session after query error: %s",
                    rollback_exc,
                )
                raise click.ClickException(
                    "Database session rollback failed after query error"
                ) from rollback_exc
            if attempt == max_attempts:
                raise click.ClickException(
                    f"Database query failed after {max_attempts} attempt(s): {exc}"
                ) from exc
            time.sleep(backoff * attempt)  # exponential backoff
    return None  # Should never reach here


def _bulk_update_with_retry(
    session: Session, model, mappings, *, max_attempts: int = 3, backoff: float = 0.5
) -> None:
    """Bulk update with retry logic and proper rollback handling."""
    for attempt in range(1, max_attempts + 1):
        try:
            session.bulk_update_mappings(model, mappings)
            return  # Success
        except SQLAlchemyError as exc:
            _LOGGER.warning(
                "Bulk update failed on attempt %d/%d: %s",
                attempt, max_attempts, exc
            )
            try:
                session.rollback()
            except Exception as rollback_exc:
                _LOGGER.error("Failed to rollback after bulk update error: %s", rollback_exc)

            if attempt == max_attempts:
                raise click.ClickException(
                    f"Bulk update failed after {max_attempts} attempt(s): {exc}"
                ) from exc
            time.sleep(backoff * attempt)  # exponential backoff


def _commit_with_retry(
    session: Session, *, max_attempts: int = 3, backoff: float = 0.5
) -> float:
    """Commit with retry logic and proper error handling."""
    for attempt in range(1, max_attempts + 1):
        try:
            commit_start = time.perf_counter()
            session.commit()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive retry path
            _LOGGER.warning(
                "Database commit failed on attempt %d/%d: %s",
                attempt, max_attempts, exc
            )
            try:
                session.rollback()
            except Exception as rollback_exc:
                _LOGGER.error("Failed to rollback after commit error: %s", rollback_exc)

            if attempt == max_attempts:
                raise click.ClickException(
                    f"Database commit failed after {max_attempts} attempt(s): {exc}"
                ) from exc
            time.sleep(backoff * attempt)
        else:
            return time.perf_counter() - commit_start
    return 0.0


@click.command("rebuild_embeddings")
@click.option("--fast", is_flag=True, help="Skip slow checks where possible.")
@click.option("--no-cache", is_flag=True, help="Ignore local caches.")
@click.option(
    "--changed-since",
    type=click.DateTime(
        formats=[
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
        ]
    ),
    help="Only rebuild passages whose parent documents changed at or after this timestamp (ISO format).",
)
@click.option(
    "--ids-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a file containing passage IDs (one per line) to rebuild.",
)
@click.option(
    "--checkpoint-file",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Persist progress to this file so long-running runs can resume later.",
)
@click.option(
    "--metrics-file",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write aggregate throughput metrics to this JSON file.",
)
@click.option(
    "--resume/--fresh",
    default=False,
    help="Resume from an existing checkpoint file instead of starting from scratch.",
)
@click.option(
    "--strict-checkpoint/--lenient-checkpoint",
    default=False,
    help="Fail on invalid checkpoint content instead of treating as missing (strict mode).",
)
def rebuild_embeddings_cmd(
    fast: bool,
    no_cache: bool,
    changed_since: datetime | None,
    ids_file: Path | None,
    checkpoint_file: Path | None,
    metrics_file: Path | None,
    resume: bool,
    strict_checkpoint: bool,
) -> None:
    """Rebuild vector store from normalized artifacts."""

    _ensure_cli_telemetry()

    from theo.infrastructure.api.app.ingest.sanitizer import sanitize_passage_text

    try:
        engine_candidate, registry = resolve_application()
        service = registry.resolve("embedding_rebuild_service")
    except Exception as exc:  # pragma: no cover - defensive
        raise click.ClickException(f"Failed to resolve application: {exc}") from exc

    if not isinstance(service, EmbeddingRebuildService):
        raise click.ClickException("Embedding rebuild service unavailable")

    try:
        engine = registry.resolve("engine")
    except Exception:
        engine = engine_candidate
    if engine is None:
        raise click.ClickException("Database engine unavailable")

    batch_size = 64 if fast else 128
    config = EmbeddingRebuildConfig.for_mode(fast=fast)
    batch_size = config.initial_batch_size
    embedding_service = get_embedding_service()
    if no_cache:
        clear_embedding_cache()

    start = time.perf_counter()
    processed = 0
    total = 0

    normalized_changed_since = _normalise_timestamp(changed_since)
    ids: Sequence[str] | None = None
    if ids_file is not None:
        ids = _load_ids(ids_file)
        if not ids:
            # Convert this to a proper error for automation/CI contexts
            raise click.ClickException("No passage IDs were found in the provided file.")

    checkpoint_state: EmbeddingCheckpoint | None = None
    skip_count = 0
    last_processed_id: str | None = None

    if checkpoint_file is not None:
        if resume:
            try:
                checkpoint_state = load_checkpoint(
                    checkpoint_file, strict=strict_checkpoint
                )
                if checkpoint_state is None and strict_checkpoint:
                    raise click.ClickException(
                        f"Checkpoint file {checkpoint_file} is missing but strict mode was enabled"
                    )
            except CheckpointError as exc:
                _LOGGER.error(
                    "Failed to load checkpoint file during resume",
                    extra={
                        "event": "cli.rebuild_embeddings.checkpoint_validation_error",
                        "checkpoint_file": str(checkpoint_file),
                    },
                    exc_info=exc,
                )
                raise click.ClickException(
                    f"Checkpoint file {checkpoint_file} is invalid: {exc}"
                ) from exc
            skip_count = checkpoint_state.processed if checkpoint_state else 0
            if skip_count:
                click.echo(
                    f"Resuming from checkpoint at {checkpoint_file} "
                    f"(already processed {skip_count} passage(s))."
                )
        else:
            try:
                checkpoint_file.unlink()
            except FileNotFoundError:
                pass
    processed = checkpoint_state.processed if checkpoint_state else 0
    if checkpoint_state:
        last_processed_id = checkpoint_state.last_id

    metadata = {
        "fast": fast,
        "changed_since": normalized_changed_since.isoformat()
        if normalized_changed_since
        else None,
        "ids_file": str(ids_file) if ids_file else None,
        "ids_count": len(ids) if ids else None,
        "resume": resume,
    }

    checkpoint_written = False

    def _on_start(start: EmbeddingRebuildStart) -> None:
        if start.missing_ids:
            click.echo(
                f"{len(start.missing_ids)} passage ID(s) were not found and will be skipped."
            )
        if start.total == 0:
            # This should also be an error in automation contexts
            # when specific criteria were given but no work was found
            if ids_file or normalized_changed_since:
                raise click.ClickException(
                    "No passages matched the specified criteria for embedding updates."
                )
            click.echo("No passages require embedding updates.")
        else:
            click.echo(
                f"Rebuilding embeddings for {start.total} passage(s) "
                f"using batch size {batch_size}."
            )

    def _on_progress(progress: EmbeddingRebuildProgress) -> None:
        nonlocal checkpoint_written
        click.echo(
            f"Batch {progress.batch_index}: updated {progress.state.processed}/"
            f"{progress.state.total} passages in {progress.batch_duration:.2f}s "
            f"({progress.rate_per_passage:.3f}s/pass)"
        )
        if checkpoint_file is not None:
            _write_checkpoint(
                checkpoint_file,
                processed=progress.state.processed,
                total=progress.state.total,
                last_id=progress.state.last_id,
                metadata=dict(progress.state.metadata),
            )
            checkpoint_written = True

    options = EmbeddingRebuildOptions(
        fast=fast,
        batch_size=batch_size,
        changed_since=normalized_changed_since,
        ids=ids,
        skip_count=skip_count,
        metadata=metadata,
        clear_cache=no_cache,
    )

    try:
        result: EmbeddingRebuildResult = service.rebuild_embeddings(
            options,
            on_start=_on_start,
            on_progress=_on_progress,
        )
    except EmbeddingRebuildError as exc:
        raise click.ClickException(str(exc)) from exc

    if result.total == 0:
        # Check if this was due to invalid input that should be an error
        if ids_file or normalized_changed_since:
            raise click.ClickException(
                "No passages matched the specified criteria for embedding updates."
            )
        return

    if checkpoint_file is not None and checkpoint_written:
        click.echo(f"Checkpoint written to {checkpoint_file}")

    # Continue with the rest of the original implementation...
    # (The rest remains the same as the original file)
    where_clause = Passage.embedding.is_(None) if fast else None

    workflow_name = "embedding_rebuild"
    telemetry_mode = "fast" if fast else "full"
    workflow_attributes = {
        "mode": telemetry_mode,
        "batch_size": batch_size,
        "resume": resume,
        "no_cache": no_cache,
        "changed_since": normalized_changed_since.isoformat()
        if normalized_changed_since
        else None,
        "ids_count": len(ids) if ids else None,
        "skip_count": skip_count if resume else 0,
    }

    with instrument_workflow(workflow_name, **workflow_attributes) as span:
        set_span_attribute(span, "embedding_rebuild.batch_size", batch_size)
        set_span_attribute(span, "embedding_rebuild.mode", telemetry_mode)
        set_span_attribute(span, "embedding_rebuild.processed", processed)
        if skip_count:
            set_span_attribute(span, "embedding_rebuild.resume.skip_count", skip_count)
        processed = min(processed, total)

        log_workflow_event(
            "embedding_rebuild.initialising",
            workflow=workflow_name,
            batch_size=batch_size,
            resume=resume,
            skip_count=skip_count,
            ids_count=len(ids) if ids else None,
            changed_since=normalized_changed_since.isoformat()
            if normalized_changed_since
            else None,
        )

        with Session(engine) as session:
            try:
                filters: list = []
                join_document = False
                if where_clause is not None:
                    filters.append(where_clause)
                if normalized_changed_since is not None:
                    join_document = True
                    filters.append(Document.updated_at >= normalized_changed_since)
                if ids:
                    filters.append(Passage.id.in_(ids))

                count_stmt = select(func.count(Passage.id)).select_from(Passage)
                if join_document:
                    count_stmt = count_stmt.join(Document)
                for criterion in filters:
                    count_stmt = count_stmt.where(criterion)

                # Use retry logic for count query
                count_result = _execute_with_retry(session, count_stmt)
                total = count_result.scalar_one()

                set_span_attribute(span, "embedding_rebuild.total", total)

                if total == 0:
                    log_workflow_event(
                        "embedding_rebuild.noop",
                        workflow=workflow_name,
                        reason="no_passages",
                    )
                    click.echo("No passages require embedding updates.")
                    return

                if ids:
                    id_check_stmt = select(Passage.id).where(Passage.id.in_(ids))
                    id_result = _execute_with_retry(session, id_check_stmt)
                    expected_ids = set(id_result.scalars())
                    missing_ids = [item for item in ids if item not in expected_ids]
                    if missing_ids:
                        click.echo(
                            f"{len(missing_ids)} passage ID(s) were not found and will be skipped."
                        )
                        log_workflow_event(
                            "embedding_rebuild.missing_ids",
                            workflow=workflow_name,
                            missing=len(missing_ids),
                        )

                log_workflow_event(
                    "embedding_rebuild.planning",
                    workflow=workflow_name,
                    total=total,
                    batch_size=batch_size,
                )
                click.echo(
                    f"Rebuilding embeddings for {total} passage(s) using batch size {batch_size}."
                )

                stmt = (
                    select(Passage)
                    .order_by(Passage.id)
                    .execution_options(stream_results=True, yield_per=batch_size)
                )
                if where_clause is not None:
                    stmt = stmt.where(where_clause)
                if join_document:
                    stmt = stmt.join(Document)
                for criterion in filters:
                    if criterion is where_clause:
                        continue  # already applied
                    stmt = stmt.where(criterion)

                # Use retry logic for streaming query
                stream_result = _execute_with_retry(session, stmt)
                stream = stream_result.scalars()

                if skip_count:
                    stream = itertools.islice(stream, skip_count, None)
                    processed = min(skip_count, total)
                    set_span_attribute(span, "embedding_rebuild.processed", processed)
                    log_workflow_event(
                        "embedding_rebuild.resumed",
                        workflow=workflow_name,
                        processed=processed,
                        total=total,
                    )

                metadata = {
                    "fast": fast,
                    "changed_since": normalized_changed_since.isoformat()
                    if normalized_changed_since
                    else None,
                    "ids_file": str(ids_file) if ids_file else None,
                    "ids_count": len(ids) if ids else None,
                    "resume": resume,
                }

                for batch_index, batch in enumerate(
                    _batched(stream, batch_size), start=1
                ):
                    if not batch:
                        continue

                    log_workflow_event(
                        "embedding_rebuild.batch_started",
                        workflow=workflow_name,
                        batch_index=batch_index,
                        batch_size=len(batch),
                        processed=processed,
                        total=total,
                    )

                    texts = [sanitize_passage_text(item.text or "") for item in batch]
                    batch_start = time.perf_counter()
                    try:
                        vectors = embedding_service.embed(texts, batch_size=batch_size)
                    except Exception as exc:  # pragma: no cover - defensive
                        log_workflow_event(
                            "embedding_rebuild.batch_failed",
                            workflow=workflow_name,
                            batch_index=batch_index,
                            error=str(exc),
                        )
                        raise click.ClickException(
                            f"Embedding generation failed: {exc}"
                        ) from exc

                    if len(vectors) != len(batch):
                        raise click.ClickException(
                            "Embedding backend returned mismatched batch size"
                        )

                    payload = [
                        {"id": passage.id, "embedding": list(vector)}
                        for passage, vector in zip(batch, vectors)
                    ]

                    # Use retry logic for bulk update
                    _bulk_update_with_retry(session, Passage, payload)
                    commit_latency = _commit_with_retry(session)

                    processed += len(batch)
                    batch_duration = time.perf_counter() - batch_start
                    rate = batch_duration / len(batch)
                    throughput = (len(batch) / batch_duration) if batch_duration else 0.0

                    record_histogram(
                        EMBEDDING_REBUILD_BATCH_LATENCY_METRIC,
                        value=batch_duration,
                        labels={"mode": telemetry_mode, "batch_size": len(batch)},
                    )
                    record_histogram(
                        EMBEDDING_REBUILD_COMMIT_LATENCY_METRIC,
                        value=commit_latency,
                        labels={"mode": telemetry_mode},
                    )
                    record_counter(
                        EMBEDDING_REBUILD_PROGRESS_METRIC,
                        amount=len(batch),
                        labels={"mode": telemetry_mode},
                    )

                    set_span_attribute(span, "embedding_rebuild.processed", processed)

                    log_workflow_event(
                        "embedding_rebuild.batch_completed",
                        workflow=workflow_name,
                        batch_index=batch_index,
                        processed=processed,
                        total=total,
                        batch_duration_ms=round(batch_duration * 1000, 2),
                        commit_latency_ms=round(commit_latency * 1000, 2),
                        throughput_per_sec=round(throughput, 2),
                    )

                    click.echo(
                        f"Batch {batch_index}: updated {processed}/{total} passages "
                        f"in {batch_duration:.2f}s ({rate:.3f}s/pass)"
                    )

                    if checkpoint_file is not None:
                        last_id = batch[-1].id
                        _write_checkpoint(
                            checkpoint_file,
                            processed=processed,
                            total=total,
                            last_id=last_id,
                            metadata=metadata,
                        )
                        log_workflow_event(
                            "embedding_rebuild.checkpoint_updated",
                            workflow=workflow_name,
                            checkpoint=str(checkpoint_file),
                            processed=processed,
                            last_id=last_id,
                        )

            except SQLAlchemyError as exc:
                _LOGGER.error(
                    "Database error during embedding rebuild: %s",
                    exc, exc_info=True
                )
                raise click.ClickException(
                    f"Database operation failed: {exc}"
                ) from exc
            except Exception as exc:
                _LOGGER.error(
                    "Unexpected error during embedding rebuild: %s",
                    exc, exc_info=True
                )
                raise
            finally:
                # Ensure session cleanup
                try:
                    session.rollback()
                except Exception:
                    pass  # Best effort cleanup

        if checkpoint_file is not None:
            click.echo(f"Checkpoint written to {checkpoint_file}")
            log_workflow_event(
                "embedding_rebuild.checkpoint_written",
                workflow=workflow_name,
                checkpoint=str(checkpoint_file),
                processed=processed,
                total=total,
            )

        duration = time.perf_counter() - start
        set_span_attribute(
            span, "embedding_rebuild.duration_ms", round(duration * 1000, 2)
        )
        log_workflow_event(
            "embedding_rebuild.completed",
            workflow=workflow_name,
            processed=processed,
            total=total,
            duration_ms=round(duration * 1000, 2),
        )

    duration = time.perf_counter() - start
    click.echo(
        f"Completed embedding rebuild for {processed} passage(s) "
        f"in {duration:.2f}s."
    )


def register_commands(cli: click.Group) -> None:
    """Register the embedding rebuild command with the provided CLI group."""

    cli.add_command(rebuild_embeddings_cmd)
