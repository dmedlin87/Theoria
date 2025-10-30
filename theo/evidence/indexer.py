"""Index builders for evidence datasets."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import EvidenceCollection, EvidenceRecord
from .validator import EvidenceValidator


class EvidenceIndexer:
    """Build searchable indexes from validated evidence records."""

    def __init__(self, validator: EvidenceValidator | None = None) -> None:
        self.validator = validator or EvidenceValidator()

    def build_sqlite(
        self,
        sources: Iterable[Path | str],
        *,
        sqlite_path: Path | str,
    ) -> EvidenceCollection:
        """Validate ``sources`` and persist them into a SQLite index."""

        collection = self.validator.validate_many(sources)
        database_path = Path(sqlite_path)
        if not database_path.parent.exists():
            database_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_sqlite(database_path, collection.records)
        return collection

    def _write_sqlite(self, path: Path, records: Iterable[EvidenceRecord]) -> None:
        serialized = list(records)
        deduped: list[EvidenceRecord] = []
        seen_sids: set[str] = set()
        for record in serialized:
            if record.sid in seen_sids:
                continue
            seen_sids.add(record.sid)
            deduped.append(record)
        with sqlite3.connect(path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    sid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT,
                    osis TEXT NOT NULL,
                    normalized_osis TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    citation TEXT,
                    metadata TEXT NOT NULL
                )
                """
            )
            cursor.execute("DELETE FROM evidence")
            for record in deduped:
                cursor.execute(
                    """
                    INSERT INTO evidence (sid, title, summary, osis, normalized_osis, tags, citation, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.sid,
                        record.title,
                        record.summary,
                        json.dumps(record.osis),
                        json.dumps(record.normalized_osis),
                        json.dumps(record.tags),
                        json.dumps(record.citation.model_dump(mode="json") if record.citation else None),
                        json.dumps(record.metadata),
                    ),
                )
            connection.commit()

    def query(
        self,
        sqlite_path: Path | str,
        *,
        osis: str | None = None,
        tag: str | None = None,
    ) -> list[EvidenceRecord]:
        """Query a SQLite index and return matching records."""

        database_path = Path(sqlite_path)
        if not database_path.exists():
            msg = f"SQLite index not found: {database_path}"
            raise FileNotFoundError(msg)

        with sqlite3.connect(database_path) as connection:
            cursor = connection.cursor()
            query = "SELECT sid, title, summary, osis, normalized_osis, tags, citation, metadata FROM evidence"
            clauses: list[str] = []
            params: list[Any] = []
            if osis:
                clauses.append("normalized_osis LIKE ?")
                params.append(f"%{osis}%")
            if tag:
                clauses.append("tags LIKE ?")
                params.append(f"%{tag}%")
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY sid"
            rows = cursor.execute(query, params).fetchall()

        results: list[EvidenceRecord] = []
        for row in rows:
            raw = {
                "sid": row[0],
                "title": row[1],
                "summary": row[2],
                "osis": json.loads(row[3]),
                "normalized_osis": tuple(json.loads(row[4])),
                "tags": tuple(json.loads(row[5])),
                "citation": json.loads(row[6]) if row[6] else None,
                "metadata": json.loads(row[7]),
            }
            results.append(EvidenceRecord.model_validate(raw))
        return results


__all__ = ["EvidenceIndexer"]
