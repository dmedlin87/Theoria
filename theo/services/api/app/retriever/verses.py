"""Verse aggregation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import Integer, cast, exists, false, func, select
from sqlalchemy.orm import Session, joinedload

from ..db.models import Document, Passage
from ..ingest.osis import expand_osis_reference
from ..models.base import Passage as PassageSchema
from ..models.verses import (
    VerseMention,
    VerseMentionsFilters,
    VerseTimelineBucket,
    VerseTimelineResponse,
)
from .utils import compose_passage_meta


def _snippet(text: str, max_length: int = 280) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _resolve_query_ids(osis: str) -> list[int]:
    """Expand *osis* into stable verse identifiers."""

    try:
        return list(sorted(expand_osis_reference(osis)))
    except Exception:  # pragma: no cover - defensive guard for malformed input
        return []


def _verse_overlap_clause(column, verse_ids: list[int], dialect_name: str):
    """Return a SQL expression testing overlap with *verse_ids*."""

    if not verse_ids:
        return None

    if dialect_name == "postgresql":
        return column.op("&&")(verse_ids)

    if dialect_name == "sqlite":
        json_each = func.json_each(column).table_valued("key", "value")
        return exists(
            select(1)
            .select_from(json_each)
            .where(cast(json_each.c.value, Integer).in_(verse_ids))
        )

    return column.isnot(None)


def get_mentions_for_osis(
    session: Session,
    osis: str,
    filters: VerseMentionsFilters | None = None,
) -> list[VerseMention]:
    """Return passages whose OSIS reference intersects the requested range."""

    verse_ids = _resolve_query_ids(osis)
    if not verse_ids:
        return []

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    overlap_clause = _verse_overlap_clause(Passage.osis_verse_ids, verse_ids, dialect_name)
    if overlap_clause is None:
        return []

    stmt = (
        select(Passage)
        .join(Document, Passage.document)
        .options(joinedload(Passage.document))
        .where(Passage.osis_verse_ids.isnot(None))
        .where(overlap_clause)
    )
    if filters:
        if filters.source_type:
            stmt = stmt.where(Document.source_type == filters.source_type)
        if filters.collection:
            stmt = stmt.where(Document.collection == filters.collection)

    result = session.execute(
        stmt.execution_options(stream_results=True, yield_per=128)
    )
    mentions: list[VerseMention] = []
    for passage in result.scalars():
        document = passage.document
        if document is None:
            continue

        if filters and filters.author:
            authors = document.authors or []
            if filters.author not in authors:
                continue

        passage_schema = PassageSchema(
            id=passage.id,
            document_id=passage.document_id,
            text=passage.text,
            osis_ref=passage.osis_ref,
            page_no=passage.page_no,
            t_start=passage.t_start,
            t_end=passage.t_end,
            meta=compose_passage_meta(passage, document),
            score=None,
        )
        mention = VerseMention(
            passage=passage_schema, context_snippet=_snippet(passage.text)
        )
        mentions.append(mention)

    mentions.sort(
        key=lambda item: (
            item.passage.meta.get("document_title") if item.passage.meta else "",
            item.passage.page_no or 0,
            item.passage.t_start or 0.0,
        )
    )
    return mentions


_WINDOW_TYPES: tuple[Literal["week", "month", "quarter", "year"], ...] = (
    "week",
    "month",
    "quarter",
    "year",
)


def _period_bounds(moment: date, window: Literal["week", "month", "quarter", "year"]):
    if window == "week":
        start_date = moment - timedelta(days=moment.weekday())
        end_date = start_date + timedelta(days=7)
        year, week_no, _ = start_date.isocalendar()
        label = f"{year}-W{week_no:02d}"
    elif window == "month":
        start_date = moment.replace(day=1)
        month_index = (start_date.month % 12) + 1
        year_offset = start_date.year + (start_date.month // 12)
        end_date = date(year_offset if month_index != 1 else start_date.year + 1, month_index, 1)
        label = start_date.strftime("%Y-%m")
    elif window == "quarter":
        quarter = (moment.month - 1) // 3 + 1
        start_month = 3 * (quarter - 1) + 1
        start_date = moment.replace(month=start_month, day=1)
        if quarter == 4:
            end_date = date(start_date.year + 1, 1, 1)
        else:
            end_date = date(start_date.year, start_month + 3, 1)
        label = f"{start_date.year}-Q{quarter}"
    else:  # year
        start_date = moment.replace(month=1, day=1)
        end_date = date(start_date.year + 1, 1, 1)
        label = str(start_date.year)

    start = datetime.combine(start_date, time.min, tzinfo=UTC)
    end = datetime.combine(end_date, time.min, tzinfo=UTC)
    return label, start, end



@dataclass
class _BucketData:
    label: str
    start: datetime
    end: datetime
    count: int = 0
    document_ids: set[str] = field(default_factory=set)
    sample_passage_ids: set[str] = field(default_factory=set)


def get_verse_timeline(
    session: Session,
    osis: str,
    window: Literal["week", "month", "quarter", "year"] = "month",
    limit: int | None = None,
    filters: VerseMentionsFilters | None = None,
) -> VerseTimelineResponse:
    if window not in _WINDOW_TYPES:
        raise ValueError(f"Unsupported timeline window: {window}")

    verse_ids = _resolve_query_ids(osis)
    if not verse_ids:
        return VerseTimelineResponse(
            osis=osis,
            window=window,
            buckets=[],
            total_mentions=0,
        )

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    overlap_clause = _verse_overlap_clause(Passage.osis_verse_ids, verse_ids, dialect_name)

    stmt = (
        select(Passage)
        .join(Document, Passage.document)
        .options(joinedload(Passage.document))
        .where(Passage.osis_verse_ids.isnot(None))
    )

    if overlap_clause is not None:
        stmt = stmt.where(overlap_clause)
    else:
        stmt = stmt.where(false())

    if filters:
        if filters.source_type:
            stmt = stmt.where(Document.source_type == filters.source_type)
        if filters.collection:
            stmt = stmt.where(Document.collection == filters.collection)

    result = session.execute(
        stmt.execution_options(stream_results=True, yield_per=256)
    )
    bucket_map: dict[datetime, _BucketData] = {}

    for passage in result.scalars():
        document = passage.document
        if document is None:
            continue

        if filters and filters.author:
            authors = document.authors or []
            if filters.author not in authors:
                continue

        reference_date = document.pub_date or (
            document.created_at.date() if document.created_at else None
        )
        if not reference_date:
            continue

        label, start, end = _period_bounds(reference_date, window)
        bucket = bucket_map.setdefault(
            start,
            _BucketData(
                label=label,
                start=start,
                end=end,
            ),
        )
        bucket.count = int(bucket.count) + 1
        bucket.document_ids.add(document.id)
        bucket.sample_passage_ids.add(passage.id)

    sorted_keys = sorted(bucket_map.keys())
    if limit is not None and limit > 0:
        sorted_keys = sorted_keys[-limit:]

    buckets: list[VerseTimelineBucket] = []
    for key in sorted_keys:
        data = bucket_map[key]
        buckets.append(
            VerseTimelineBucket(
                label=data.label,
                start=data.start,
                end=data.end,
                count=int(data.count),
                document_ids=sorted(data.document_ids),
                sample_passage_ids=sorted(data.sample_passage_ids),
            )
        )

    total_mentions = sum(bucket.count for bucket in buckets)

    return VerseTimelineResponse(
        osis=osis,
        window=window,
        buckets=buckets,
        total_mentions=total_mentions,
    )
