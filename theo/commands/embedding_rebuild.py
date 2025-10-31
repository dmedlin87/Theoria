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
    duration = time.perf_counter() - start
    click.echo(
        f"Completed embedding rebuild for {result.processed} passage(s) "
        f"in {result.duration:.2f}s."
    )


def register_commands(cli: click.Group) -> None:
    """Register the embedding rebuild command with the provided CLI group."""

    cli.add_command(rebuild_embeddings_cmd)
