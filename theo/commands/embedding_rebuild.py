"""Embedding rebuild CLI command implementation."""

from __future__ import annotations

import itertools
import json
import logging
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

import click

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
    set_span_attribute,
    set_telemetry_provider,
)
from theo.application.telemetry import EMBEDDING_REBUILD_PROGRESS_METRIC
from theo.application.embeddings.checkpoint_store import (
    CheckpointError,
    EmbeddingCheckpoint,
    load_checkpoint,
    save_checkpoint,
)
from theo.infrastructure.api.app.ingest.embeddings import clear_embedding_cache
from theo.application.services.bootstrap import resolve_application
from theo.domain.services.embeddings import EmbeddingRebuildConfig

__all__ = ["register_commands", "rebuild_embeddings_cmd", "_batched", "_commit_with_retry"]


_LOGGER = logging.getLogger(__name__)


def _default_service_provider() -> EmbeddingRebuildService:
    """Resolve the embedding rebuild service from the application container."""

    try:
        _engine, registry = resolve_application()
    except Exception as exc:  # pragma: no cover - defensive
        raise click.ClickException(f"Failed to resolve application: {exc}") from exc

    service = registry.resolve("embedding_rebuild_service")
    if not isinstance(service, EmbeddingRebuildService):
        raise click.ClickException("Embedding rebuild service unavailable")
    return service


_SERVICE_PROVIDER: Callable[[], EmbeddingRebuildService] = _default_service_provider
_CLEAR_CACHE: Callable[[], None] = clear_embedding_cache


def configure_embedding_rebuild_cli(
    *,
    service_provider: Callable[[], EmbeddingRebuildService] | None = None,
    cache_clearer: Callable[[], None] | None = None,
) -> None:
    """Override dependencies used by the CLI for testability."""

    global _SERVICE_PROVIDER, _CLEAR_CACHE
    if service_provider is None and cache_clearer is None:
        _SERVICE_PROVIDER = _default_service_provider
        _CLEAR_CACHE = clear_embedding_cache
        return
    if service_provider is not None:
        _SERVICE_PROVIDER = service_provider
    if cache_clearer is not None:
        _CLEAR_CACHE = cache_clearer


def _normalise_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


_T = TypeVar("_T")


def _batched(iterator: Iterable[_T], size: int) -> Iterable[list[_T]]:
    """Yield successive batches from iterator."""
    if size <= 0:
        raise ValueError("Batch size must be positive")
    while True:
        batch = list(itertools.islice(iterator, size))
        if not batch:
            break
        yield batch


def _commit_with_retry(
    session: object,
    *,
    max_attempts: int = 3,
    backoff: float = 0.5,
) -> float:
    """Attempt to commit a session with exponential backoff retry.

    Args:
        session: A session-like object with commit() and rollback() methods
        max_attempts: Maximum number of commit attempts
        backoff: Base delay in seconds between retries

    Returns:
        Duration of successful commit in seconds

    Raises:
        click.ClickException: If commit fails after max_attempts
    """
    from sqlalchemy.exc import SQLAlchemyError

    start = time.perf_counter()
    for attempt in range(1, max_attempts + 1):
        try:
            session.commit()  # type: ignore[attr-defined]
            return time.perf_counter() - start
        except SQLAlchemyError as exc:
            if hasattr(session, "rollback"):
                session.rollback()  # type: ignore[attr-defined]
            if attempt == max_attempts:
                raise click.ClickException(
                    f"Database commit failed after {attempt} attempt(s): {exc}"
                ) from exc
            time.sleep(backoff * attempt)
    # Should never reach here, but for type checker
    return time.perf_counter() - start  # pragma: no cover


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

    service = _SERVICE_PROVIDER()

    config = EmbeddingRebuildConfig.for_mode(fast=fast)
    batch_size = config.initial_batch_size
    if no_cache:
        _CLEAR_CACHE()

    normalized_changed_since = _normalise_timestamp(changed_since)
    ids: Sequence[str] | None = None
    if ids_file is not None:
        ids = _load_ids(ids_file)
        if not ids:
            # Convert this to a proper error for automation/CI contexts
            raise click.ClickException("No passage IDs were found in the provided file.")

    checkpoint_state: EmbeddingCheckpoint | None = None
    skip_count = 0
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

    if metrics_file is not None:
        throughput = (
            result.processed / result.duration if result.duration > 0 else None
        )
        metrics_payload: dict[str, object] = {
            "processed_passages": result.processed,
            "total_passages": result.total,
            "duration_seconds": result.duration,
            "throughput_passages_per_second": throughput,
            "missing_passage_ids": list(result.missing_ids),
            "metadata": dict(result.metadata),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        metrics_file.write_text(
            json.dumps(metrics_payload, indent=2), encoding="utf-8"
        )
        click.echo(f"Metrics written to {metrics_file}")

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

    result: EmbeddingRebuildResult | None = None

    try:
        with instrument_workflow(workflow_name, **workflow_attributes) as span:
            set_span_attribute(span, "embedding_rebuild.batch_size", batch_size)
            set_span_attribute(span, "embedding_rebuild.mode", telemetry_mode)
            if skip_count:
                set_span_attribute(
                    span, "embedding_rebuild.resume.skip_count", skip_count
                )

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

            try:
                result = service.rebuild_embeddings(
                    options,
                    on_start=_on_start,
                    on_progress=_on_progress,
                )
            except EmbeddingRebuildError as exc:
                log_workflow_event(
                    "embedding_rebuild.failed",
                    workflow=workflow_name,
                    error=str(exc),
                )
                set_span_attribute(span, "embedding_rebuild.error", str(exc))
                raise

            set_span_attribute(span, "embedding_rebuild.processed", result.processed)
            set_span_attribute(span, "embedding_rebuild.total", result.total)
            set_span_attribute(
                span,
                "embedding_rebuild.duration_ms",
                round(result.duration * 1000, 2),
            )

            record_counter(
                EMBEDDING_REBUILD_PROGRESS_METRIC,
                amount=result.processed,
                labels={"mode": telemetry_mode},
            )

            if checkpoint_file is not None and checkpoint_written:
                log_workflow_event(
                    "embedding_rebuild.checkpoint_written",
                    workflow=workflow_name,
                    checkpoint=str(checkpoint_file),
                    processed=result.processed,
                    total=result.total,
                )

            log_workflow_event(
                "embedding_rebuild.completed",
                workflow=workflow_name,
                processed=result.processed,
                total=result.total,
                duration_ms=round(result.duration * 1000, 2),
                missing_ids=len(result.missing_ids),
            )
    except EmbeddingRebuildError as exc:
        raise click.ClickException(str(exc)) from exc

    assert result is not None

    if result.total == 0:
        # Check if this was due to invalid input that should be an error
        if ids_file or normalized_changed_since:
            raise click.ClickException(
                "No passages matched the specified criteria for embedding updates."
            )
        return

    if checkpoint_file is not None and checkpoint_written:
        click.echo(f"Checkpoint written to {checkpoint_file}")

    if metrics_file is not None:
        metrics_payload: Mapping[str, object] = {
            "processed": result.processed,
            "total": result.total,
            "duration_seconds": result.duration,
            "missing_ids": result.missing_ids,
            "mode": telemetry_mode,
        }
        metrics_file.write_text(
            json.dumps(metrics_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    click.echo(
        f"Completed embedding rebuild for {result.processed} passage(s) "
        f"in {result.duration:.2f}s."
    )


def register_commands(cli: click.Group) -> None:
    """Register the embedding rebuild command with the provided CLI group."""

    cli.add_command(rebuild_embeddings_cmd)
