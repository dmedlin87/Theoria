"""Shared routing ledger backed by SQLite."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from typing import ContextManager

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

    def mark_inflight_error(self, cache_key: str, message: str) -> None:
        self._connection.execute(
            """
            UPDATE inflight_entries
            SET status='error', error=?, updated_at=?
            WHERE cache_key=?
            """,
            (message, time.time(), cache_key),
        )

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
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
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
        finally:
            connection.close()

    def _ensure_inflight_schema(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info('inflight_entries')")
        }
        if "completed_at" not in columns:
            connection.execute("ALTER TABLE inflight_entries ADD COLUMN completed_at REAL")

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
        return json.dumps(parts, separators=(",", ":"))

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
    ) -> CacheRecord:
        """Block until the inflight entry completes or raises."""

        start = time.time()

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
            row = self._read_inflight(cache_key)
            if row is None:
                # No inflight record – attempt to resolve from cache.
                with self.transaction() as txn:
                    cached = txn.get_cache_entry(cache_key)
                if cached is not None:
                    return cached
                if timeout is not None and time.time() - start > timeout:
                    raise GenerationError(
                        "Timed out waiting for inflight generation"
                    )
                time.sleep(poll_interval)
                continue
            if (
                row.output is not None
                and row.completed_at is not None
                and row.completed_at >= start
            ):
                return _row_to_record(row)
            if row.status == "waiting":
                if timeout is not None and time.time() - start > timeout:
                    raise GenerationError("Timed out waiting for inflight generation")
                time.sleep(poll_interval)
                continue
            if row.status == "success":
                return _row_to_record(row)
            if row.status == "error":
                if (
                    row.output is not None
                    and row.completed_at is not None
                    and row.completed_at >= start
                ):
                    return _row_to_record(row)
                if row.completed_at is None:
                    with self.transaction() as txn:
                        txn.clear_single_inflight(cache_key)
                raise GenerationError(row.error or "Deduplicated generation failed")
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


__all__ = ["SharedLedger", "LedgerTransaction", "CacheRecord", "InflightRow"]

