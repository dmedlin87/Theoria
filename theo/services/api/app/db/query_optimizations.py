"""Database query optimization utilities.

Provides helpers for eager loading, query batching, and performance monitoring.
"""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Load, Session, joinedload, selectinload

if TYPE_CHECKING:
    from sqlalchemy.orm import InstrumentedAttribute

from theo.application.facades.telemetry import record_counter, record_histogram

T = TypeVar("T")


def with_eager_loading(
    session: Session,
    model_class: type[T],
    *relationships: InstrumentedAttribute,
    strategy: str = "selectin",
) -> tuple[Load[Any], ...]:
    """Build eager-loading loader options for SQLAlchemy queries.

    Args:
        session: SQLAlchemy session (kept for interface symmetry; not used).
        model_class: The model class whose relationships should be eagerly loaded.
        relationships: Instrumented relationship attributes to eager load.
        strategy: Loader strategy to apply, either ``"selectin"`` (default) or ``"joined"``.

    Returns:
        Tuple of loader options to unpack into ``Query.options`` or ``Select.options``.

    Example:
        stmt = select(Document).options(
            *with_eager_loading(session, Document, Document.passages, strategy="selectin")
        )
    """
    load_strategy = selectinload if strategy == "selectin" else joinedload
    return tuple(load_strategy(rel) for rel in relationships)


def query_with_monitoring(metric_name: str):
    """Decorator to monitor query execution time and result counts.

    Usage:
        @query_with_monitoring("discovery.list_query")
        def list_discoveries(session, user_id):
            return session.execute(select(Discovery)...).all()
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time

                # Record metrics
                record_histogram(f"{metric_name}.duration_seconds", duration)

                # Count results if it's a sequence
                if isinstance(result, Sequence):
                    record_counter(f"{metric_name}.result_count", len(result))

                return result
            except Exception:
                duration = time.perf_counter() - start_time
                record_histogram(f"{metric_name}.error_duration_seconds", duration)
                raise
        return wrapper
    return decorator


def batch_load(
    session: Session,
    model_class: type[T],
    ids: Sequence[int | str],
    batch_size: int = 100,
) -> list[T]:
    """Load models in batches to avoid excessive query parameters.

    Args:
        session: SQLAlchemy session
        model_class: The model to load
        ids: List of IDs to load
        batch_size: Number of IDs per batch

    Returns:
        List of loaded models
    """
    results: list[T] = []

    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        stmt = select(model_class).where(model_class.id.in_(batch))  # type: ignore
        batch_results = list(session.scalars(stmt))
        results.extend(batch_results)

    return results


__all__ = [
    "with_eager_loading",
    "query_with_monitoring",
    "batch_load",
]
