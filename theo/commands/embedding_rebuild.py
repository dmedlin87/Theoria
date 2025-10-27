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
from theo.checkpoints import (
    CheckpointValidationError,
    EmbeddingRebuildCheckpoint,
    deserialize_embedding_rebuild_checkpoint,
    save_embedding_rebuild_checkpoint,
)
from theo.services.api.app.ingest.embeddings import (
    clear_embedding_cache,
    get_embedding_service,
)
from theo.services.bootstrap import resolve_application
from theo.services.embeddings import (
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


def _read_checkpoint(
    path: Path, *, raise_on_error: bool = False
) -> EmbeddingRebuildCheckpoint | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        if raise_on_error:
            raise
        return None

    if not isinstance(payload, Mapping):
        return None

    try:
        return deserialize_embedding_rebuild_checkpoint(payload)
    except CheckpointValidationError:
        return None


def _write_checkpoint(
    path: Path,
    *,
    processed: int,
    total: int,
    last_id: str | None,
    metadata: dict[str, object],
    previous: EmbeddingRebuildCheckpoint | None = None,
) -> EmbeddingRebuildCheckpoint:
    checkpoint = EmbeddingRebuildCheckpoint.build(
        processed=processed,
        total=total,
        last_id=last_id,
        metadata=metadata,
        previous=previous,
    )
    save_embedding_rebuild_checkpoint(path, checkpoint)
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
            from theo.services.api.app.adapters.telemetry import (
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


def _commit_with_retry(
    session: Session, *, max_attempts: int = 3, backoff: float = 0.5
) -> float:
    for attempt in range(1, max_attempts + 1):
        try:
            commit_start = time.perf_counter()
            session.commit()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive retry path
            session.rollback()
            if attempt == max_attempts:
                raise click.ClickException(
                    f"Database commit failed after {attempt} attempt(s): {exc}"
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
def rebuild_embeddings_cmd(
    fast: bool,
    no_cache: bool,
    changed_since: datetime | None,
    ids_file: Path | None,
    checkpoint_file: Path | None,
    metrics_file: Path | None,
    resume: bool,
) -> None:
    """Rebuild vector store from normalized artifacts."""

    _ensure_cli_telemetry()

    from theo.services.api.app.ingest.sanitizer import sanitize_passage_text

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
            click.echo("No passage IDs were found in the provided file.")
            return

    checkpoint_state: EmbeddingRebuildCheckpoint | None = None
    skip_count = 0
    last_processed_id: str | None = None

    if checkpoint_file is not None:
        if resume:
            try:
                checkpoint_state = _read_checkpoint(
                    checkpoint_file, raise_on_error=True
                )
            except json.JSONDecodeError as exc:
                _LOGGER.error(
                    "Failed to decode checkpoint file during resume",
                    extra={
                        "event": "cli.rebuild_embeddings.checkpoint_decode_error",
                        "checkpoint_file": str(checkpoint_file),
                    },
                    exc_info=exc,
                )
                raise click.ClickException(
                    f"Checkpoint file {checkpoint_file} contains invalid JSON"
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
        return

    if checkpoint_file is not None and checkpoint_written:
        click.echo(f"Checkpoint written to {checkpoint_file}")

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
            total = session.execute(count_stmt).scalar_one()

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
                expected_ids = set(
                    session.execute(
                        select(Passage.id).where(Passage.id.in_(ids))
                    ).scalars()
                )
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

            stream = session.execute(stmt).scalars()
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

                session.bulk_update_mappings(Passage, payload)
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
        base_stmt = select(Passage).order_by(Passage.id)
        if where_clause is not None:
            base_stmt = base_stmt.where(where_clause)
        if join_document:
            base_stmt = base_stmt.join(Document)
        for criterion in filters:
            if criterion is where_clause:
                continue
            base_stmt = base_stmt.where(criterion)

        metadata = {
            "fast": fast,
            "changed_since": normalized_changed_since.isoformat()
            if normalized_changed_since
            else None,
            "ids_file": str(ids_file) if ids_file else None,
            "ids_count": len(ids) if ids else None,
            "resume": resume,
            "config": config.to_metadata(),
            "metrics_file": str(metrics_file) if metrics_file else None,
        }

        instrumentation = EmbeddingRebuildInstrumentation()

        pending_payload: list[dict[str, object]] = []
        pending_update_count = 0
        pending_batches = 0
        batch_index = 0

        def _flush_pending(last_id_value: str | None) -> None:
            nonlocal pending_payload, pending_update_count, pending_batches
            if not pending_payload:
                return
            session.bulk_update_mappings(Passage, pending_payload)
            _commit_with_retry(session)
            instrumentation.record_commit()
            click.echo(
                f"Committed {pending_update_count} passage embedding(s); "
                f"{processed}/{total} processed."
            )
            if checkpoint_file is not None:
                last_id = batch[-1].id
                checkpoint_state = _write_checkpoint(
                    checkpoint_file,
                    processed=processed,
                    total=total,
                    last_id=last_id_value,
                    metadata=metadata,
                    previous=checkpoint_state,
                )
            pending_payload = []
            pending_update_count = 0
            pending_batches = 0

        current_batch_size = batch_size
        current_yield_size = config.compute_yield_size(current_batch_size)
        resource_probe = config.resource_probe
        click.echo(
            "Rebuilding embeddings for "
            f"{total} passage(s) with initial batch size {current_batch_size} "
            f"and commit cadence {config.commit_cadence}."
        )
        if processed:
            remaining = max(total - processed, 0)
            click.echo(
                f"{remaining} passage(s) remain after resuming from checkpoint."
            )

        while processed < total:
            stmt = base_stmt
            if last_processed_id:
                stmt = stmt.where(Passage.id > last_processed_id)
            stmt = stmt.limit(current_yield_size).execution_options(stream_results=True)
            rows = session.execute(stmt).scalars().all()
            if not rows:
                break

            offset = 0
            while offset < len(rows):
                batch = rows[offset : offset + current_batch_size]
                if not batch:
                    break
                batch_index += 1
                texts = [sanitize_passage_text(item.text or "") for item in batch]
                batch_start = time.perf_counter()
                try:
                    vectors = embedding_service.embed(texts, batch_size=len(batch))
                except Exception as exc:  # pragma: no cover - defensive
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

                pending_payload.extend(payload)
                batch_duration = time.perf_counter() - batch_start
                processed += len(batch)
                pending_update_count += len(batch)
                pending_batches += 1
                last_processed_id = str(batch[-1].id)

                snapshot = resource_probe()
                instrumentation.record_batch(
                    size=len(batch),
                    duration=batch_duration,
                    resource_snapshot=snapshot,
                )

                per_pass_duration = batch_duration / len(batch) if batch else 0.0
                click.echo(
                    f"Batch {batch_index}: processed {len(batch)} passages "
                    f"in {batch_duration:.2f}s ({per_pass_duration:.3f}s/pass)"
                )

                adjusted_batch_size = config.adjust_batch_size(
                    batch_size=current_batch_size,
                    duration=batch_duration,
                    resource_snapshot=snapshot,
                )
                if adjusted_batch_size != current_batch_size:
                    click.echo(
                        f"Adjusted batch size from {current_batch_size} to "
                        f"{adjusted_batch_size} based on resource probes."
                    )
                    current_batch_size = adjusted_batch_size
                    current_yield_size = config.compute_yield_size(current_batch_size)

                if pending_batches >= config.commit_cadence:
                    _flush_pending(last_processed_id)

                offset += len(batch)

            if last_processed_id is None and rows:
                last_processed_id = str(rows[-1].id)

        _flush_pending(last_processed_id)
        if checkpoint_file is not None:
            _write_checkpoint(
                checkpoint_file,
                processed=processed,
                total=total,
                last_id=last_processed_id,
                metadata=metadata,
            )
            click.echo(f"Checkpoint written to {checkpoint_file}")

        instrumentation.emit(echo=click.echo)
        if metrics_file is not None:
            instrumentation.dump(metrics_file)
            click.echo(f"Metrics written to {metrics_file}")

    duration = time.perf_counter() - start
    click.echo(
        f"Completed embedding rebuild for {result.processed} passage(s) "
        f"in {result.duration:.2f}s."
    )


def register_commands(cli: click.Group) -> None:
    """Register the embedding rebuild command with the provided CLI group."""

    cli.add_command(rebuild_embeddings_cmd)
