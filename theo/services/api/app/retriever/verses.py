"""Verse aggregation utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import Integer, and_, cast, exists, func, or_, select
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


@dataclass(frozen=True)
class _VerseQuery:
    verse_ids: list[int]
    start_id: int
    end_id: int


def _resolve_query_range(osis: str) -> _VerseQuery | None:
    """Expand *osis* into a canonical verse-id range."""

    try:
        ids = list(sorted(expand_osis_reference(osis)))
    except Exception:  # pragma: no cover - defensive guard for malformed input
        return None

    if not ids:
        return None

    return _VerseQuery(verse_ids=ids, start_id=ids[0], end_id=ids[-1])


def _array_overlap_clause(column, query: _VerseQuery, dialect_name: str):
    """Return a SQL expression testing overlap with *verse_ids*."""

    if dialect_name == "postgresql":
        return column.op("&&")(query.verse_ids)

    if dialect_name == "sqlite":
        json_each = func.json_each(column).table_valued("key", "value")
        return exists(
            select(1)
            .select_from(json_each)
            .where(cast(json_each.c.value, Integer).in_(query.verse_ids))
        )

    return column.isnot(None)


def _range_overlap_clause(query: _VerseQuery):
    """Return a SQL expression for overlapping verse-id ranges."""

    return and_(
        Passage.osis_start_verse_id.isnot(None),
        Passage.osis_end_verse_id.isnot(None),
        Passage.osis_start_verse_id <= query.end_id,
        Passage.osis_end_verse_id >= query.start_id,
    )


def _matches_query(passage: Passage, query: _VerseQuery) -> bool:
    """Return ``True`` when *passage* overlaps the requested verse range."""

    start = passage.osis_start_verse_id
    end = passage.osis_end_verse_id
    if start is not None and end is not None:
        return start <= query.end_id and end >= query.start_id

    verse_candidates: set[int] = set()
    if passage.osis_verse_ids:
        try:
            verse_candidates.update(int(value) for value in passage.osis_verse_ids if value is not None)
        except TypeError:  # pragma: no cover - defensive for unexpected payloads
            pass

    if not verse_candidates and passage.osis_ref:
        try:
            verse_candidates.update(expand_osis_reference(passage.osis_ref))
        except Exception:  # pragma: no cover - malformed legacy metadata
            return False

    if not verse_candidates:
        return False

    return any(query.start_id <= verse_id <= query.end_id for verse_id in verse_candidates)


def get_mentions_for_osis(
    session: Session,
    osis: str,
    filters: VerseMentionsFilters | None = None,
) -> list[VerseMention]:
    """Return passages whose OSIS reference intersects the requested range."""

    verse_query = _resolve_query_range(osis)
    if not verse_query:
        return []

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    range_clause = _range_overlap_clause(verse_query)
    array_overlap_clause = _array_overlap_clause(
        Passage.osis_verse_ids, verse_query, dialect_name
    )
    fallback_clause = None
    if array_overlap_clause is not None:
        fallback_clause = and_(
            or_(
                Passage.osis_start_verse_id.is_(None),
                Passage.osis_end_verse_id.is_(None),
            ),
            Passage.osis_verse_ids.isnot(None),
            array_overlap_clause,
        )

    stmt = (
        select(Passage)
        .join(Document, Passage.document)
        .options(joinedload(Passage.document))
    )
    if fallback_clause is not None:
        stmt = stmt.where(or_(range_clause, fallback_clause))
    else:
        stmt = stmt.where(range_clause)

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

        if not _matches_query(passage, verse_query):
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

    verse_query = _resolve_query_range(osis)
    if not verse_query:
        return VerseTimelineResponse(
            osis=osis,
            window=window,
            buckets=[],
            total_mentions=0,
        )

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    range_clause = _range_overlap_clause(verse_query)
    array_overlap_clause = _array_overlap_clause(
        Passage.osis_verse_ids, verse_query, dialect_name
    )
    fallback_clause = None
    if array_overlap_clause is not None:
        fallback_clause = and_(
            or_(
                Passage.osis_start_verse_id.is_(None),
                Passage.osis_end_verse_id.is_(None),
            ),
            Passage.osis_verse_ids.isnot(None),
            array_overlap_clause,
        )

    stmt = (
        select(Passage)
        .join(Document, Passage.document)
        .options(joinedload(Passage.document))
    )

    if fallback_clause is not None:
        stmt = stmt.where(or_(range_clause, fallback_clause))
    else:
        stmt = stmt.where(range_clause)

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

        if not _matches_query(passage, verse_query):
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
