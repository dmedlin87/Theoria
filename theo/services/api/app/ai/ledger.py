"""Shared routing ledger backed by SQLite."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from typing import ContextManager

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter
except Exception:  # pragma: no cover - metrics disabled
    Counter = None  # type: ignore[assignment]

from .clients import GenerationError


@dataclass
class CacheRecord:
    """Serialized cached generation stored in the ledger."""

    cache_key: str
    model_name: str
    workflow: str
    prompt: str
    temperature: float
    max_output_tokens: int
    output: str
    latency_ms: float
    cost: float
    created_at: float


@dataclass
class InflightRow:
    """Representation of an inflight entry."""

    cache_key: str
    status: str
    model_name: str | None
    workflow: str | None
    output: str | None
    latency_ms: float | None
    cost: float | None
    error: str | None
    updated_at: float
    completed_at: float | None


logger = logging.getLogger(__name__)


class _NoopCounter:
    """Fallback counter used when Prometheus metrics are unavailable."""

    def labels(self, *args: object, **kwargs: object) -> "_NoopCounter":
        return self

    def inc(self, amount: float = 1.0) -> None:
        return None


if Counter is not None:  # pragma: no cover - exercised when metrics available
    _LEDGER_STATE_TRANSITIONS = Counter(
        "theo_router_ledger_state_transitions_total",
        "Observed deduplicated inflight state transitions.",
        labelnames=("status",),
    )
    _LEDGER_EVENTS = Counter(
        "theo_router_ledger_events_total",
        "Observed ledger wait events for deduplicated generations.",
        labelnames=("event",),
    )
else:  # pragma: no cover - metrics disabled
    _LEDGER_STATE_TRANSITIONS = _NoopCounter()
    _LEDGER_EVENTS = _NoopCounter()


def _record_event(event: str, cache_key: str, **extra: object) -> None:
    """Record an observability event for inflight wait handling."""

    logger.debug(
        "ledger.wait.%s",
        event,
        extra={"cache_key": cache_key, **extra},
    )
    try:
        _LEDGER_EVENTS.labels(event=event).inc()
    except Exception:  # pragma: no cover - defensive guard
        logger.debug("failed to record ledger metric", exc_info=True)


class LedgerTransaction:
    """Transactional view over the shared ledger tables."""

    def __init__(self, ledger: "SharedLedger", connection: sqlite3.Connection) -> None:
        self._ledger = ledger
        self._connection = connection

    # ------------------------------------------------------------------
    # Spend and latency metrics
    # ------------------------------------------------------------------
    def get_spend(self, model_name: str) -> float:
        row = self._connection.execute(
            "SELECT amount FROM spend WHERE model = ?",
            (model_name,),
        ).fetchone()
        return float(row[0]) if row is not None else 0.0

    def set_spend(self, model_name: str, amount: float) -> None:
        self._connection.execute(
            """
            INSERT INTO spend(model, amount)
            VALUES(?, ?)
            ON CONFLICT(model) DO UPDATE SET amount = excluded.amount
            """,
            (model_name, float(amount)),
        )

    def clear_spend(self) -> None:
        self._connection.execute("DELETE FROM spend")

    def get_latency(self, model_name: str) -> float | None:
        row = self._connection.execute(
            "SELECT value FROM latency WHERE model = ?",
            (model_name,),
        ).fetchone()
        return float(row[0]) if row is not None else None

    def get_all_spend(self) -> dict[str, float]:
        """Get spending for all models."""
        rows = self._connection.execute("SELECT model, amount FROM spend").fetchall()
        return {row[0]: float(row[1]) for row in rows}

    def get_all_latency(self) -> dict[str, float]:
        """Get latency for all models."""
        rows = self._connection.execute("SELECT model, value FROM latency").fetchall()
        return {row[0]: float(row[1]) for row in rows}

    def set_latency(self, model_name: str, latency_ms: float) -> None:
        self._connection.execute(
            """
            INSERT INTO latency(model, value, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(model) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (model_name, float(latency_ms), time.time()),
        )

    def clear_latency(self) -> None:
        self._connection.execute("DELETE FROM latency")

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    def get_cache_entry(self, cache_key: str) -> CacheRecord | None:
        row = self._connection.execute(
            """
            SELECT cache_key, model_name, workflow, prompt, temperature, max_output_tokens,
                   output, latency_ms, cost, created_at
            FROM cache_entries
            WHERE cache_key = ?
            """,
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        return CacheRecord(
            cache_key=row[0],
            model_name=row[1],
            workflow=row[2],
            prompt=row[3],
            temperature=float(row[4]),
            max_output_tokens=int(row[5]),
            output=row[6],
            latency_ms=float(row[7]),
            cost=float(row[8]),
            created_at=float(row[9]),
        )

    def purge_expired_cache(self, now: float, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return
        self._connection.execute(
            "DELETE FROM cache_entries WHERE ? - created_at > ?",
            (now, ttl_seconds),
        )

    def cache_size(self) -> int:
        (count,) = self._connection.execute(
            "SELECT COUNT(*) FROM cache_entries"
        ).fetchone()
        return int(count)

    def pop_oldest_cache_entry(self) -> None:
        row = self._connection.execute(
            "SELECT cache_key FROM cache_entries ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if row is not None:
            (key,) = row
            self._connection.execute(
                "DELETE FROM cache_entries WHERE cache_key = ?",
                (key,),
            )

    def store_cache_entry(self, record: CacheRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO cache_entries(
                cache_key, model_name, workflow, prompt, temperature, max_output_tokens,
                output, latency_ms, cost, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                model_name = excluded.model_name,
                workflow = excluded.workflow,
                prompt = excluded.prompt,
                temperature = excluded.temperature,
                max_output_tokens = excluded.max_output_tokens,
                output = excluded.output,
                latency_ms = excluded.latency_ms,
                cost = excluded.cost,
                created_at = excluded.created_at
            """,
            (
                record.cache_key,
                record.model_name,
                record.workflow,
                record.prompt,
                float(record.temperature),
                int(record.max_output_tokens),
                record.output,
                float(record.latency_ms),
                float(record.cost),
                float(record.created_at),
            ),
        )

    def clear_cache(self) -> None:
        self._connection.execute("DELETE FROM cache_entries")

    # ------------------------------------------------------------------
    # Inflight helpers
    # ------------------------------------------------------------------
    def get_inflight(self, cache_key: str) -> InflightRow | None:
        row = self._connection.execute(
            """
            SELECT cache_key, status, model_name, workflow, output, latency_ms, cost, error, updated_at, completed_at
            FROM inflight_entries
            WHERE cache_key = ?
            """,
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        return InflightRow(
            cache_key=row[0],
            status=row[1],
            model_name=row[2],
            workflow=row[3],
            output=row[4],
            latency_ms=float(row[5]) if row[5] is not None else None,
            cost=float(row[6]) if row[6] is not None else None,
            error=row[7],
            updated_at=float(row[8]),
            completed_at=float(row[9]) if row[9] is not None else None,
        )

    def create_inflight(self, cache_key: str, *, model_name: str, workflow: str) -> None:
        self._connection.execute(
            """
            INSERT INTO inflight_entries(cache_key, status, model_name, workflow, updated_at, completed_at)
            VALUES(?, 'waiting', ?, ?, ?, NULL)
            ON CONFLICT(cache_key) DO UPDATE SET
                status='waiting',
                model_name=excluded.model_name,
                workflow=excluded.workflow,
                error=NULL,
                updated_at=excluded.updated_at
            """,
            (cache_key, model_name, workflow, time.time()),
        )

    def mark_inflight_success(
        self,
        cache_key: str,
        *,
        model_name: str,
        workflow: str,
        output: str,
        latency_ms: float,
        cost: float,
    ) -> None:
        timestamp = time.time()
        self._connection.execute(
            """
            UPDATE inflight_entries
            SET status='success', model_name=?, workflow=?, output=?,
                latency_ms=?, cost=?, error=NULL, updated_at=?, completed_at=?
            WHERE cache_key=?
            """,
            (
                model_name,
                workflow,
                output,
                float(latency_ms),
                float(cost),
                timestamp,
                timestamp,
                cache_key,
            ),
        )
        record = CacheRecord(
            cache_key=cache_key,
            model_name=model_name,
            workflow=workflow,
            prompt="",
            temperature=0.0,
            max_output_tokens=0,
            output=output,
            latency_ms=float(latency_ms),
            cost=float(cost),
            created_at=timestamp,
        )
        self._ledger._store_preserved(record)

    def mark_inflight_error(self, cache_key: str, message: str) -> None:
        timestamp = time.time()
        self._connection.execute(
            """
            UPDATE inflight_entries
                SET
                    status=CASE WHEN status='success' THEN status ELSE 'error' END,
                    error=CASE WHEN status='success' THEN error ELSE ? END,
                    updated_at=CASE WHEN status='success' THEN updated_at ELSE ? END
            WHERE cache_key=?
            """,
            (message, timestamp, cache_key),
        )

    def hydrate_waiting_from_preserved(
        self, cache_key: str, record: CacheRecord
    ) -> bool:
        """Populate a waiting inflight row with a preserved success payload."""

        row = self.get_inflight(cache_key)
        if row is None or row.status != "waiting":
            return False
        if (
            row.output is not None
            and row.completed_at is not None
            and row.completed_at >= record.created_at
        ):
            return False

        updated_at = max(row.updated_at, record.created_at)
        self._connection.execute(
            """
            UPDATE inflight_entries
            SET
                output=?,
                latency_ms=?,
                cost=?,
                completed_at=?,
                error=NULL,
                updated_at=?
            WHERE cache_key=? AND status='waiting'
            """,
            (
                record.output,
                float(record.latency_ms),
                float(record.cost),
                float(record.created_at),
                float(updated_at),
                cache_key,
            ),
        )
        return True

    def clear_inflight(self) -> None:
        self._connection.execute("DELETE FROM inflight_entries")

    def clear_single_inflight(self, cache_key: str) -> None:
        self._connection.execute(
            "DELETE FROM inflight_entries WHERE cache_key = ?",
            (cache_key,),
        )


class SharedLedger:
    """Persistent routing ledger accessed by all router instances."""

    def __init__(self, path: str | None = None) -> None:
        default_path = Path(tempfile.gettempdir()) / "theo_router_ledger.db"
        if path is not None:
            resolved_path = Path(path)
        else:
            env_path = os.environ.get("THEO_ROUTER_LEDGER_PATH")
            resolved_path = Path(env_path) if env_path else default_path
        self._path = resolved_path
        if self._path.parent and not self._path.parent.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._preserved_lock = threading.Lock()
        self._preserved_records: dict[str, CacheRecord] = {}
        self._initialize()

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._path,
            timeout=30.0,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            # Enable WAL mode for better concurrency
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            # Optimize for concurrent reads/writes
            connection.execute("PRAGMA cache_size=-64000")  # 64MB cache
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS spend (
                    model TEXT PRIMARY KEY,
                    amount REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS latency (
                    model TEXT PRIMARY KEY,
                    value REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    temperature REAL NOT NULL,
                    max_output_tokens INTEGER NOT NULL,
                    output TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    cost REAL NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS inflight_entries (
                    cache_key TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    model_name TEXT,
                    workflow TEXT,
                    output TEXT,
                    latency_ms REAL,
                    cost REAL,
                    error TEXT,
                    updated_at REAL NOT NULL,
                    completed_at REAL
                );
                """
            )
            self._ensure_inflight_schema(connection)
            self._create_indexes(connection)
        finally:
            connection.close()

    def _ensure_inflight_schema(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info('inflight_entries')")
        }
        if "completed_at" not in columns:
            connection.execute("ALTER TABLE inflight_entries ADD COLUMN completed_at REAL")

    def _create_indexes(self, connection: sqlite3.Connection) -> None:
        """Create indexes for frequently queried columns."""
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_cache_created_at ON cache_entries(created_at);
            CREATE INDEX IF NOT EXISTS idx_inflight_status ON inflight_entries(status);
            CREATE INDEX IF NOT EXISTS idx_inflight_updated_at ON inflight_entries(updated_at);
            """
        )

    def _store_preserved(self, record: CacheRecord) -> None:
        with self._preserved_lock:
            self._preserved_records[record.cache_key] = record

    def _get_preserved(self, cache_key: str) -> CacheRecord | None:
        with self._preserved_lock:
            return self._preserved_records.get(cache_key)

    def _clear_preserved(self, cache_key: str) -> None:
        with self._preserved_lock:
            self._preserved_records.pop(cache_key, None)

    # ------------------------------------------------------------------
    # Transaction handling
    # ------------------------------------------------------------------
    def transaction(self) -> ContextManager[LedgerTransaction]:
        """Return a context manager providing a transactional ledger view."""

        class _LedgerTransactionContext:
            def __init__(self, outer: "SharedLedger") -> None:
                self._outer = outer

            def __enter__(self) -> LedgerTransaction:
                self._outer._lock.acquire()
                self._connection = self._outer._connect()
                self._connection.execute("BEGIN IMMEDIATE")
                return LedgerTransaction(self._outer, self._connection)

            def __exit__(self, exc_type, exc, tb) -> None:
                try:
                    if exc_type is None:
                        self._connection.commit()
                    else:
                        self._connection.rollback()
                finally:
                    self._connection.close()
                    self._outer._lock.release()

        return _LedgerTransactionContext(self)

    # ------------------------------------------------------------------
    # Cache key helpers
    # ------------------------------------------------------------------
    @staticmethod
    def encode_cache_key(parts: tuple[str, str, str, float, int]) -> str:
        model_name, workflow, prompt, temperature, max_tokens = parts
        content = f"{model_name}:{workflow}:{temperature}:{max_tokens}:{prompt}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    # ------------------------------------------------------------------
    # Inflight waiting utilities
    # ------------------------------------------------------------------
    def _read_inflight(self, cache_key: str) -> InflightRow | None:
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT cache_key, status, model_name, workflow, output, latency_ms, cost, error, updated_at, completed_at
                FROM inflight_entries
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
            if row is None:
                return None
            return InflightRow(
                cache_key=row[0],
                status=row[1],
                model_name=row[2],
                workflow=row[3],
                output=row[4],
                latency_ms=float(row[5]) if row[5] is not None else None,
                cost=float(row[6]) if row[6] is not None else None,
                error=row[7],
                updated_at=float(row[8]),
                completed_at=float(row[9]) if row[9] is not None else None,
            )
        finally:
            connection.close()

    def wait_for_inflight(
        self,
        cache_key: str,
        *,
        poll_interval: float = 0.05,
        timeout: float | None = None,
        observed_updated_at: float | None = None,
    ) -> CacheRecord:
        """Block until the inflight entry completes or raises.

        Args:
            cache_key: Unique identifier for the generation request
            poll_interval: How often to check status (seconds)
            timeout: Maximum wait time before raising (seconds)
            observed_updated_at: Initial timestamp to detect stale entries

        Returns:
            CacheRecord containing the completed generation

        Raises:
            GenerationError: If timeout occurs or generation fails
        """

        start = time.time()
        comparison_floor = observed_updated_at if observed_updated_at is not None else start
        # Anchor the minimum timestamp a preserved success must meet so that
        # later inflight updates (for example, a restarted router recreating a
        # "waiting" row) do not mask an already-committed result.
        delivery_floor = comparison_floor
        deadline = start + timeout if timeout is not None else None
        # Remember the latest error so timeout handling can surface a useful
        # message. We only clear stale inflight rows after the caller's timeout
        # to ensure the original owner can still update the shared record.
        last_error_message: str | None = None
        last_status: str | None = None
        last_updated_at: float | None = None
        missing_logged = False
        preserved_record = self._get_preserved(cache_key)
        preserved_completed_at: float | None = (
            preserved_record.created_at if preserved_record is not None else None
        )
        success_missing_output_since: float | None = None

        def _can_use_preserved(*, include_unobserved: bool = False) -> bool:
            if preserved_record is None:
                return False
            if preserved_completed_at is None:
                return True
            if observed_updated_at is None:
                return include_unobserved
            return preserved_completed_at >= delivery_floor

        def _row_to_record(row: InflightRow) -> CacheRecord:
            created_at = row.completed_at or row.updated_at
            return CacheRecord(
                cache_key=row.cache_key,
                model_name=row.model_name or "",
                workflow=row.workflow or "",
                prompt="",
                temperature=0.0,
                max_output_tokens=0,
                output=row.output or "",
                latency_ms=row.latency_ms or 0.0,
                cost=row.cost or 0.0,
                created_at=created_at,
            )

        while True:
            now = time.time()
            if deadline is not None and now >= deadline:
                if _can_use_preserved(include_unobserved=True):
                    _record_event(
                        "delivered",
                        cache_key,
                        source="preserved",
                        status=last_status,
                    )
                    return preserved_record
                # Only purge stale inflight entries once we know the owning
                # router can no longer update them.
                _record_event(
                    "timeout",
                    cache_key,
                    status=last_status,
                    observed_updated_at=observed_updated_at,
                )
                with self.transaction() as txn:
                    txn.clear_single_inflight(cache_key)
                error_msg = (
                    f"Timed out waiting for inflight generation (key: {cache_key[:8]}..., "
                    f"status: {last_status}, elapsed: {now - start:.1f}s)"
                )
                if last_error_message:
                    error_msg = f"{error_msg}: {last_error_message}"
                raise GenerationError(error_msg)
            row = self._read_inflight(cache_key)
            shared_preserved = self._get_preserved(cache_key)
            if shared_preserved is not None and (
                preserved_record is None
                or shared_preserved.created_at >= (preserved_completed_at or shared_preserved.created_at)
            ):
                preserved_record = shared_preserved
                preserved_completed_at = shared_preserved.created_at
            if row is None:
                # No inflight record – attempt to resolve from cache.
                if not missing_logged:
                    _record_event("missing_row", cache_key)
                    missing_logged = True
                with self.transaction() as txn:
                    cached = txn.get_cache_entry(cache_key)
                if cached is not None:
                    _record_event("cache_hit", cache_key, source="cache")
                    return cached
                if _can_use_preserved(include_unobserved=True):
                    _record_event(
                        "delivered",
                        cache_key,
                        source="preserved",
                        status=last_status,
                    )
                    return preserved_record
                time.sleep(poll_interval)
                continue
            else:
                if missing_logged:
                    _record_event("row_reappeared", cache_key)
                    missing_logged = False
                if observed_updated_at is None:
                    observed_updated_at = row.updated_at
                    # Ensure preserved completions that predate this waiter
                    # remain eligible when we encounter earlier update times.
                    delivery_floor = min(delivery_floor, observed_updated_at)
                if (
                    row.output is not None
                    and row.completed_at is not None
                    and (
                        preserved_completed_at is None
                        or row.completed_at >= preserved_completed_at
                    )
                ):
                    preserved_completed_at = row.completed_at
                    preserved_record = _row_to_record(row)
                    self._store_preserved(preserved_record)
                    if preserved_completed_at is not None:
                        delivery_floor = min(delivery_floor, preserved_completed_at)
                    last_error_message = None
                    if preserved_completed_at is not None and preserved_completed_at >= start:
                        if row.status == "waiting":
                            _record_event(
                                "delivered",
                                cache_key,
                                source="preserved",
                                status=row.status,
                            )
                            return preserved_record
                    if (
                        row.status == "waiting"
                        and _can_use_preserved(include_unobserved=True)
                    ):
                        _record_event(
                            "delivered",
                            cache_key,
                            source="preserved",
                            status=row.status,
                        )
                        return preserved_record
                if row.updated_at < comparison_floor:
                    _record_event(
                        "stale_row",
                        cache_key,
                        status=row.status,
                        updated_at=row.updated_at,
                        comparison_floor=comparison_floor,
                    )
                    comparison_floor = row.updated_at
                    delivery_floor = min(delivery_floor, comparison_floor)
                if (
                    last_status != row.status
                    or last_updated_at is None
                    or row.updated_at > last_updated_at
                ):
                    _record_event(
                        "state_transition",
                        cache_key,
                        status=row.status,
                        updated_at=row.updated_at,
                    )
                    try:
                        _LEDGER_STATE_TRANSITIONS.labels(status=row.status).inc()
                    except Exception:  # pragma: no cover - defensive guard
                        logger.debug("failed to record ledger state metric", exc_info=True)
                    last_status = row.status
                    last_updated_at = row.updated_at
            if (
                row.status in {"success", "error"}
                and row.output is not None
                and (
                    row.completed_at is None
                    or row.completed_at >= comparison_floor
                )
            ):
                if row.status == "success":
                    last_error_message = None
                _record_event(
                    "delivered",
                    cache_key,
                    source="ledger",
                    status=row.status,
                )
                success_missing_output_since = None
                return _row_to_record(row)
            if row.status == "waiting":
                if preserved_record is not None and (
                    row.output is None
                    or row.completed_at is None
                    or (
                        preserved_completed_at is not None
                        and (row.completed_at or 0.0) < preserved_completed_at
                    )
                ):
                    rehydrated = False
                    with self.transaction() as txn:
                        rehydrated = txn.hydrate_waiting_from_preserved(
                            cache_key, preserved_record
                        )
                    if rehydrated:
                        _record_event(
                            "rehydrated_waiting",
                            cache_key,
                            status=row.status,
                        )
                        # Refresh the inflight row so that any waiters observe
                        # the preserved payload on the next iteration.
                        row = self._read_inflight(cache_key)
                        shared_preserved = self._get_preserved(cache_key)
                        if shared_preserved is not None and (
                            preserved_record is None
                            or shared_preserved.created_at
                            >= (preserved_completed_at or shared_preserved.created_at)
                        ):
                            preserved_record = shared_preserved
                            preserved_completed_at = shared_preserved.created_at
                        if row is None:
                            time.sleep(poll_interval)
                            continue
                        continue
                if _can_use_preserved():
                    if preserved_record is not None and row.output is None:
                        refreshed = self._read_inflight(cache_key)
                        shared_preserved = self._get_preserved(cache_key)
                        if shared_preserved is not None and (
                            preserved_record is None
                            or shared_preserved.created_at
                            >= (preserved_completed_at or shared_preserved.created_at)
                        ):
                            preserved_record = shared_preserved
                            preserved_completed_at = shared_preserved.created_at
                        if refreshed is not None:
                            row = refreshed
                            if row.status == "waiting" and row.output is not None:
                                time.sleep(0)
                                continue
                    _record_event(
                        "delivered",
                        cache_key,
                        source="preserved",
                        status=row.status,
                    )
                    success_missing_output_since = None
                    return preserved_record
                if (
                    observed_updated_at is not None
                    and row.updated_at > observed_updated_at
                ):
                    with self.transaction() as txn:
                        cached = txn.get_cache_entry(cache_key)
                    if cached is not None:
                        return cached
                    if not (
                        row.output is not None
                        and row.completed_at is not None
                    ):
                        comparison_floor = row.updated_at
                        delivery_floor = min(delivery_floor, comparison_floor)
                    observed_updated_at = row.updated_at
                    delivery_floor = min(delivery_floor, observed_updated_at)
                time.sleep(poll_interval)
                continue
            if row.status == "success":
                if row.output is not None:
                    last_error_message = None
                    _record_event(
                        "delivered",
                        cache_key,
                        source="ledger",
                        status=row.status,
                    )
                    success_missing_output_since = None
                    return _row_to_record(row)
                with self.transaction() as txn:
                    cached = txn.get_cache_entry(cache_key)
                if cached is not None:
                    _record_event("cache_hit", cache_key, source="cache")
                    success_missing_output_since = None
                    return cached
                if success_missing_output_since is None:
                    success_missing_output_since = now
                    _record_event(
                        "success_missing_output",
                        cache_key,
                        status=row.status,
                    )
                logger.warning(
                    "Inflight success for %s missing output; waiting for owner to finish",
                    cache_key,
                )
                time.sleep(poll_interval)
                continue
            if row.status == "error":
                last_error_message = row.error or "Deduplicated generation failed"
                if (
                    observed_updated_at is not None
                    and row.updated_at > observed_updated_at
                ):
                    with self.transaction() as txn:
                        cached = txn.get_cache_entry(cache_key)
                    if cached is not None:
                        _record_event("cache_hit", cache_key, source="cache")
                        return cached
                    comparison_floor = row.updated_at
                    observed_updated_at = row.updated_at
                if (
                    row.output is None
                    or row.completed_at is None
                    or row.completed_at < comparison_floor
                ):
                    if _can_use_preserved(include_unobserved=True):
                        _record_event(
                            "delivered",
                            cache_key,
                            source="preserved_after_error",
                            status=row.status,
                        )
                        success_missing_output_since = None
                        return preserved_record
                    # A transient failure was observed, but the owning router may
                    # still be retrying. Keep polling instead of clearing the row so
                    # all waiters eventually share the successful output.
                    if success_missing_output_since is not None:
                        _record_event(
                            "awaiting_success_output",
                            cache_key,
                            status=row.status,
                        )
                    _record_event(
                        "transient_error",
                        cache_key,
                        status=row.status,
                        error=row.error,
                    )
                    time.sleep(poll_interval)
                    continue
                # Preserve the inflight row so earlier waiters that began
                # before a restart can still observe the preserved success
                # payload. Clearing the entry here would race with those
                # callers and drop the cached result before they can reuse it.
                with self.transaction() as txn:
                    cached = txn.get_cache_entry(cache_key)
                if cached is not None:
                    _record_event("cache_hit", cache_key, source="cache")
                    success_missing_output_since = None
                    return cached
                if _can_use_preserved(include_unobserved=True):
                    _record_event(
                        "delivered",
                        cache_key,
                        source="preserved",
                        status=row.status,
                    )
                    success_missing_output_since = None
                    return preserved_record
                _record_event(
                    "error_raised",
                    cache_key,
                    status=row.status,
                    error=row.error,
                )
                raise GenerationError(last_error_message)
            _record_event(
                "unknown_state",
                cache_key,
                status=row.status,
                updated_at=row.updated_at,
            )
            raise GenerationError(f"Unknown inflight status: {row.status}")

    # ------------------------------------------------------------------
    # Maintenance helpers
    # ------------------------------------------------------------------
    def reset(self) -> None:
        with self.transaction() as txn:
            txn.clear_spend()
            txn.clear_latency()
            txn.clear_cache()
            txn.clear_inflight()
        with self._preserved_lock:
            self._preserved_records.clear()


__all__ = ["SharedLedger", "LedgerTransaction", "CacheRecord", "InflightRow"]

