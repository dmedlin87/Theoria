"""Verse aggregation utilities."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, cast as typing_cast

from sqlalchemy import Date, DateTime, Integer, cast, case, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..db.models import Document, Passage, PassageVerse
from ..ingest.osis import canonical_verse_range, expand_osis_reference
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


def _document_ids_for_author(
    session: Session,
    verse_ids: list[int],
    author: str,
    *,
    range_start: int | None = None,
    range_end: int | None = None,
) -> list[str]:
    """Return document identifiers mentioning *author* within *verse_ids*."""

    if not author:
        return []

    candidate_ids: set[str] = set()

    if range_start is not None and range_end is not None:
        range_stmt = (
            select(Document.id, Document.authors)
            .join(Passage, Document.passages)
            .where(Passage.osis_start_verse_id.isnot(None))
            .where(Passage.osis_end_verse_id.isnot(None))
            .where(Passage.osis_start_verse_id <= range_end)
            .where(Passage.osis_end_verse_id >= range_start)
            .distinct()
        )
        for doc_id, authors in session.execute(range_stmt):
            if isinstance(authors, list) and author in authors:
                candidate_ids.add(doc_id)

    if verse_ids:
        legacy_stmt = (
            select(Document.id, Document.authors)
            .join(Passage, Document.passages)
            .join(PassageVerse, PassageVerse.passage_id == Passage.id)
            .where(PassageVerse.verse_id.in_(verse_ids))
            .where(
                or_(
                    Passage.osis_start_verse_id.is_(None),
                    Passage.osis_end_verse_id.is_(None),
                )
            )
            .distinct()
        )
        for doc_id, authors in session.execute(legacy_stmt):
            if isinstance(authors, list) and author in authors:
                candidate_ids.add(doc_id)

    return sorted(candidate_ids)


def _normalize_verse_ids(values: list[int] | list[object] | None) -> list[int]:
    """Normalize a sequence of potential verse identifiers to integers."""

    normalized: list[int] = []
    if not values:
        return normalized
    for value in values:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError):  # pragma: no cover - defensive guards
            continue
    return normalized


def _extract_passage_references(passage: Passage) -> list[str]:
    """Collect OSIS reference strings associated with *passage*."""

    references: set[str] = set()
    if passage.osis_ref:
        references.add(passage.osis_ref)

    meta = passage.meta
    if isinstance(meta, dict):
        for key in (
            "primary_osis",
            "osis_refs_all",
            "osis_refs_detected",
            "osis_refs_hints",
            "osis_refs_unmatched",
        ):
            value = meta.get(key)
            if isinstance(value, str):
                if value:
                    references.add(value)
            elif isinstance(value, (list, tuple, set)):
                for item in value:
                    if item:
                        references.add(str(item))

    return sorted(ref for ref in references if ref)


def _passage_overlaps_range(
    passage: Passage,
    range_start: int,
    range_end: int,
) -> bool:
    """Determine whether *passage* intersects the requested verse id range."""

    start_id = passage.osis_start_verse_id
    end_id = passage.osis_end_verse_id
    if start_id is not None and end_id is not None:
        return start_id <= range_end and end_id >= range_start

    normalized_ids = _normalize_verse_ids(passage.osis_verse_ids)
    if normalized_ids:
        return min(normalized_ids) <= range_end and max(normalized_ids) >= range_start

    references = _extract_passage_references(passage)
    _, start, end = canonical_verse_range(references)
    if start is not None and end is not None:
        return start <= range_end and end >= range_start

    if passage.osis_ref:
        try:
            expanded = expand_osis_reference(passage.osis_ref)
        except Exception:  # pragma: no cover - defensive guard
            expanded = frozenset()
        if expanded:
            expanded_list = sorted(expanded)
            return expanded_list[0] <= range_end and expanded_list[-1] >= range_start

    return False


def _parse_aggregated_ids(value: object, dialect_name: str) -> list[str]:
    """Normalise aggregated identifier payloads from SQL into sorted strings."""

    if value is None:
        return []
    if dialect_name == "postgresql" and isinstance(value, (list, tuple)):
        candidates = [item for item in value if item]
    elif isinstance(value, str):
        candidates = [item for item in value.split(",") if item]
    elif isinstance(value, (list, tuple, set)):
        candidates = [item for item in value if item]
    else:
        candidates = [value] if value else []

    return sorted({str(item) for item in candidates})


def _coerce_bucket_start(value: object) -> date | None:
    """Convert SQL bucket values into ``date`` instances."""

    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:  # pragma: no cover - defensive
            return None
    return None




def _legacy_overlap_clause(column, verse_ids: list[int], dialect_name: str):
    """Return a SQL expression mirroring the legacy array overlap logic."""

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


def _bucket_start_expression(
    window: Literal["week", "month", "quarter", "year"],
    dialect_name: str,
):
    """Return a SQL expression yielding the bucket start date for *window*."""

    if dialect_name == "sqlite":
        reference_date = func.coalesce(Document.pub_date, func.date(Document.created_at))
        weekday = cast(func.strftime("%w", reference_date), Integer)

        if window == "week":
            return case(
                (weekday == 0, func.date(reference_date, "-6 day")),
                (weekday == 1, reference_date),
                (weekday == 2, func.date(reference_date, "-1 day")),
                (weekday == 3, func.date(reference_date, "-2 day")),
                (weekday == 4, func.date(reference_date, "-3 day")),
                (weekday == 5, func.date(reference_date, "-4 day")),
                (weekday == 6, func.date(reference_date, "-5 day")),
                else_=reference_date,
            )

        if window == "month":
            return func.date(reference_date, "start of month")

        if window == "quarter":
            month = cast(func.strftime("%m", reference_date), Integer)
            quarter_start = case(
                (month <= 3, "01"),
                (month <= 6, "04"),
                (month <= 9, "07"),
                else_="10",
            )
            return func.date(
                func.printf("%s-%s-01", func.strftime("%Y", reference_date), quarter_start)
            )

        return func.date(func.printf("%s-01-01", func.strftime("%Y", reference_date)))

    reference_ts = func.coalesce(cast(Document.pub_date, DateTime), Document.created_at)
    if window == "week":
        bucket_ts = func.date_trunc("week", reference_ts)
    elif window == "month":
        bucket_ts = func.date_trunc("month", reference_ts)
    elif window == "quarter":
        bucket_ts = func.date_trunc("quarter", reference_ts)
    else:
        bucket_ts = func.date_trunc("year", reference_ts)

    return cast(bucket_ts, Date)


def _timeline_from_passages(
    passages: Iterable[Passage],
    filters: VerseMentionsFilters | None,
    window: Literal["week", "month", "quarter", "year"],
    limit: int | None,
) -> tuple[list[VerseTimelineBucket], int]:
    """Aggregate *passages* into timeline buckets respecting optional filters."""

    bucket_map: dict[datetime, dict[str, object]] = {}
    for passage in passages:
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

        label, start_dt, end_dt = _period_bounds(reference_date, window)
        data = bucket_map.setdefault(
            start_dt,
            {
                "label": label,
                "start": start_dt,
                "end": end_dt,
                "count": 0,
                "docs": set(),
                "passages": set(),
            },
        )
        data["count"] = int(data["count"]) + 1
        typing_cast(set, data["docs"]).add(document.id)
        typing_cast(set, data["passages"]).add(passage.id)

    sorted_keys = sorted(bucket_map.keys())
    if limit and limit > 0:
        sorted_keys = sorted_keys[-limit:]

    buckets: list[VerseTimelineBucket] = []
    total_mentions = 0
    for key in sorted_keys:
        data = bucket_map[key]
        count = int(data["count"])
        total_mentions += count
        buckets.append(
            VerseTimelineBucket(
                label=data["label"],
                start=data["start"],
                end=data["end"],
                count=count,
                document_ids=sorted(typing_cast(set, data["docs"])),
                sample_passage_ids=sorted(typing_cast(set, data["passages"])),
            )
        )

    return buckets, total_mentions


def get_mentions_for_osis(
    session: Session,
    osis: str,
    filters: VerseMentionsFilters | None = None,
) -> list[VerseMention]:
    """Return passages whose OSIS reference intersects the requested range."""

    verse_ids = _resolve_query_ids(osis)
    if not verse_ids:
        return []

    range_start, range_end = verse_ids[0], verse_ids[-1]

    base_stmt = (
        select(Passage)
        .join(Document, Passage.document)
        .options(joinedload(Passage.document))
    )

    allowed_doc_ids: list[str] | None = None
    if filters:
        if filters.source_type:
            base_stmt = base_stmt.where(Document.source_type == filters.source_type)
        if filters.collection:
            base_stmt = base_stmt.where(Document.collection == filters.collection)
        if filters.author:
            allowed_doc_ids = _document_ids_for_author(
                session,
                verse_ids,
                filters.author,
                range_start=range_start,
                range_end=range_end,
            )
            if not allowed_doc_ids:
                return []
            base_stmt = base_stmt.where(Document.id.in_(allowed_doc_ids))

    range_stmt = base_stmt.where(Passage.osis_start_verse_id.isnot(None))
    range_stmt = range_stmt.where(Passage.osis_end_verse_id.isnot(None))
    range_stmt = range_stmt.where(Passage.osis_start_verse_id <= range_end)
    range_stmt = range_stmt.where(Passage.osis_end_verse_id >= range_start)

    result = session.execute(range_stmt.execution_options(stream_results=True))
    passages = list(result.scalars().unique())
    seen_ids = {passage.id for passage in passages}

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    overlap_clause = _legacy_overlap_clause(Passage.osis_verse_ids, verse_ids, dialect_name)
    if overlap_clause is not None:
        legacy_stmt = (
            base_stmt.where(
                or_(
                    Passage.osis_start_verse_id.is_(None),
                    Passage.osis_end_verse_id.is_(None),
                )
            )
            .where(Passage.osis_verse_ids.isnot(None))
            .where(overlap_clause)
        )
        legacy_result = session.execute(
            legacy_stmt.execution_options(stream_results=True)
        )
        for passage in legacy_result.scalars().unique():
            if passage.id not in seen_ids:
                passages.append(passage)
                seen_ids.add(passage.id)

    python_stmt = (
        base_stmt.where(
            or_(
                Passage.osis_start_verse_id.is_(None),
                Passage.osis_end_verse_id.is_(None),
            )
        )
        .where(Passage.osis_verse_ids.is_(None))
        .where(Passage.osis_ref.isnot(None))
    )
    python_result = session.execute(
        python_stmt.execution_options(stream_results=True)
    )
    for passage in python_result.scalars().unique():
        if passage.id in seen_ids:
            continue
        if _passage_overlaps_range(passage, range_start, range_end):
            passages.append(passage)
            seen_ids.add(passage.id)

    mentions: list[VerseMention] = []
    for passage in passages:
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





def _legacy_timeline(
    session: Session,
    verse_ids: list[int],
    filters: VerseMentionsFilters | None,
    window: Literal["week", "month", "quarter", "year"],
    limit: int | None,
    dialect_name: str,
    *,
    allowed_doc_ids: list[str] | None,
) -> tuple[list[VerseTimelineBucket], int]:
    overlap_clause = _legacy_overlap_clause(Passage.osis_verse_ids, verse_ids, dialect_name)
    if overlap_clause is None:
        return [], 0

    stmt = (
        select(Passage)
        .join(Document, Passage.document)
        .options(joinedload(Passage.document))
        .where(Passage.osis_verse_ids.isnot(None))
        .where(
            or_(
                Passage.osis_start_verse_id.is_(None),
                Passage.osis_end_verse_id.is_(None),
            )
        )
        .where(overlap_clause)
    )

    if filters:
        if filters.source_type:
            stmt = stmt.where(Document.source_type == filters.source_type)
        if filters.collection:
            stmt = stmt.where(Document.collection == filters.collection)

    if allowed_doc_ids:
        stmt = stmt.where(Document.id.in_(allowed_doc_ids))

    result = session.execute(stmt.execution_options(stream_results=True))
    passages = list(result.scalars().unique())

    return _timeline_from_passages(passages, filters, window, limit)


def _python_timeline(
    session: Session,
    filters: VerseMentionsFilters | None,
    window: Literal["week", "month", "quarter", "year"],
    limit: int | None,
    *,
    range_start: int,
    range_end: int,
    allowed_doc_ids: list[str] | None,
) -> tuple[list[VerseTimelineBucket], int]:
    """Fallback timeline builder when verse identifiers are stored only in metadata."""

    stmt = (
        select(Passage)
        .join(Document, Passage.document)
        .options(joinedload(Passage.document))
        .where(
            or_(
                Passage.osis_start_verse_id.is_(None),
                Passage.osis_end_verse_id.is_(None),
            )
        )
        .where(Passage.osis_verse_ids.is_(None))
        .where(Passage.osis_ref.isnot(None))
        .where(func.coalesce(Document.pub_date, Document.created_at).isnot(None))
    )

    if filters:
        if filters.source_type:
            stmt = stmt.where(Document.source_type == filters.source_type)
        if filters.collection:
            stmt = stmt.where(Document.collection == filters.collection)

    if allowed_doc_ids:
        stmt = stmt.where(Document.id.in_(allowed_doc_ids))

    result = session.execute(stmt.execution_options(stream_results=True))
    passages = [
        passage
        for passage in result.scalars().unique()
        if _passage_overlaps_range(passage, range_start, range_end)
    ]

    if not passages:
        return [], 0

    return _timeline_from_passages(passages, filters, window, limit)


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

    range_start, range_end = verse_ids[0], verse_ids[-1]

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""

    bucket_start = _bucket_start_expression(window, dialect_name).label("bucket_start")
    mention_count = func.count(func.distinct(Passage.id)).label("mention_count")
    if dialect_name == "postgresql":
        document_ids_expr = func.array_agg(func.distinct(Document.id)).label("document_ids")
        passage_ids_expr = func.array_agg(func.distinct(Passage.id)).label("passage_ids")
    else:
        document_ids_expr = func.group_concat(func.distinct(Document.id)).label("document_ids")
        passage_ids_expr = func.group_concat(func.distinct(Passage.id)).label("passage_ids")

    stmt = (
        select(bucket_start, mention_count, document_ids_expr, passage_ids_expr)
        .join(Document, Passage.document)
        .where(Passage.osis_start_verse_id.isnot(None))
        .where(Passage.osis_end_verse_id.isnot(None))
        .where(Passage.osis_start_verse_id <= range_end)
        .where(Passage.osis_end_verse_id >= range_start)
        .where(func.coalesce(Document.pub_date, Document.created_at).isnot(None))
    )

    allowed_doc_ids: list[str] | None = None
    if filters:
        if filters.source_type:
            stmt = stmt.where(Document.source_type == filters.source_type)
        if filters.collection:
            stmt = stmt.where(Document.collection == filters.collection)
        if filters.author:
            allowed_doc_ids = _document_ids_for_author(
                session,
                verse_ids,
                filters.author,
                range_start=range_start,
                range_end=range_end,
            )
            if not allowed_doc_ids:
                return VerseTimelineResponse(osis=osis, window=window, buckets=[], total_mentions=0)
            stmt = stmt.where(Document.id.in_(allowed_doc_ids))

    stmt = stmt.group_by(bucket_start).order_by(bucket_start)

    rows = session.execute(stmt).all()

    bucket_records: list[tuple[datetime, int, VerseTimelineBucket]] = []
    for bucket_value, count_value, doc_values, passage_values in rows:
        bucket_date = _coerce_bucket_start(bucket_value)
        if not bucket_date:
            continue

        label, start_dt, end_dt = _period_bounds(bucket_date, window)
        document_ids = _parse_aggregated_ids(doc_values, dialect_name)
        passage_ids = _parse_aggregated_ids(passage_values, dialect_name)
        count_int = int(count_value or 0)
        bucket_records.append(
            (
                start_dt,
                count_int,
                VerseTimelineBucket(
                    label=label,
                    start=start_dt,
                    end=end_dt,
                    count=count_int,
                    document_ids=document_ids,
                    sample_passage_ids=passage_ids,
                ),
            )
        )

    if not bucket_records:
        legacy_buckets, legacy_total = _legacy_timeline(
            session=session,
            verse_ids=verse_ids,
            filters=filters,
            window=window,
            limit=limit,
            dialect_name=dialect_name,
            allowed_doc_ids=allowed_doc_ids,
        )
        if legacy_buckets:
            return VerseTimelineResponse(
                osis=osis,
                window=window,
                buckets=legacy_buckets,
                total_mentions=legacy_total,
            )

        python_buckets, python_total = _python_timeline(
            session=session,
            filters=filters,
            window=window,
            limit=limit,
            range_start=range_start,
            range_end=range_end,
            allowed_doc_ids=allowed_doc_ids,
        )
        if python_buckets:
            return VerseTimelineResponse(
                osis=osis,
                window=window,
                buckets=python_buckets,
                total_mentions=python_total,
            )

    if limit and limit > 0:
        bucket_records = bucket_records[-limit:]

    buckets = [bucket for _, _, bucket in bucket_records]
    total_mentions = sum(count for _, count, _ in bucket_records)

    return VerseTimelineResponse(
        osis=osis,
        window=window,
        buckets=buckets,
        total_mentions=total_mentions,
    )
