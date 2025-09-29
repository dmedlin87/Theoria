"""Service helpers for managing personal watchlists and alert generation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Document, Passage, UserWatchlist, WatchlistEvent
from ..models.watchlists import (
    WatchlistCreateRequest,
    WatchlistFilters,
    WatchlistMatch,
    WatchlistResponse,
    WatchlistRunResponse,
    WatchlistUpdateRequest,
)

DEFAULT_LOOKBACK = timedelta(days=7)
CADENCE_WINDOWS: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}


def _normalise_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _load_filters(raw: dict | list | None) -> WatchlistFilters:
    if isinstance(raw, dict):
        return WatchlistFilters.model_validate(raw)
    return WatchlistFilters()


def _watchlist_to_response(watchlist: UserWatchlist) -> WatchlistResponse:
    filters = _load_filters(watchlist.filters)
    channels = _normalise_list(watchlist.delivery_channels)
    return WatchlistResponse(
        id=watchlist.id,
        user_id=watchlist.user_id,
        name=watchlist.name,
        filters=filters,
        cadence=watchlist.cadence,
        delivery_channels=channels,
        is_active=watchlist.is_active,
        last_run=watchlist.last_run,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
    )


def _match_topics(document: Document, filters: WatchlistFilters) -> bool:
    if not filters.topics:
        return True
    desired = {topic.lower() for topic in filters.topics}
    topics: set[str] = set()
    if isinstance(document.topics, list):
        topics.update(str(item).lower() for item in document.topics)
    elif isinstance(document.topics, dict):
        topics.update(str(value).lower() for value in document.topics.values())
    if isinstance(document.bib_json, dict):
        bib_topics = document.bib_json.get("topics")
        if isinstance(bib_topics, list):
            topics.update(str(item).lower() for item in bib_topics)
        primary = document.bib_json.get("primary_topic")
        if isinstance(primary, str):
            topics.add(primary.lower())
    return bool(topics & desired)


def _match_authors(document: Document, filters: WatchlistFilters) -> bool:
    if not filters.authors:
        return True
    desired = {author.lower() for author in filters.authors}
    authors: set[str] = set()
    if isinstance(document.authors, list):
        authors.update(str(item).lower() for item in document.authors)
    return bool(authors & desired)


def _match_keywords(document: Document, filters: WatchlistFilters) -> bool:
    if not filters.keywords:
        return True
    haystack = " ".join(
        part.lower()
        for part in [document.title or "", document.abstract or ""]
        if part
    )
    if not haystack:
        return False
    return any(keyword.lower() in haystack for keyword in filters.keywords)


def _normalise_metadata_values(value: object) -> list[str]:
    """Flatten metadata values to lower-cased strings for comparison."""

    if value is None:
        return []
    if isinstance(value, str):
        return [value.lower()]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_normalise_metadata_values(item))
        return result
    if isinstance(value, (int, float, bool)):
        return [str(value).lower()]
    if isinstance(value, Iterable):
        result: list[str] = []
        for item in value:
            result.extend(_normalise_metadata_values(item))
        return result
    return [str(value).lower()]


def _match_metadata(document: Document, filters: WatchlistFilters) -> bool:
    """Return ``True`` when document metadata satisfies requested filters.

    Metadata filters perform case-insensitive equality checks against the
    document fields and any bibliographic metadata stored in ``bib_json``.
    Iterable filter values (lists/sets/tuples) must all be present in the
    document metadata, while scalar values require a single exact match.
    Nested structures (lists/dicts) in the document metadata are flattened
    before comparison, so partial string containment is **not** supported.
    """

    if not filters.metadata:
        return True

    doc_metadata: dict[str, list[str]] = {}

    def _append_values(key: str, value: object) -> None:
        if value is None:
            return
        doc_metadata.setdefault(key, []).extend(_normalise_metadata_values(value))

    for key in filters.metadata:
        attr_value = getattr(document, key, None)
        _append_values(key, attr_value)
        if isinstance(document.bib_json, dict) and key in document.bib_json:
            _append_values(key, document.bib_json.get(key))

    for key, raw_expected in filters.metadata.items():
        expected = _normalise_metadata_values(raw_expected)
        if not expected:
            continue
        observed = doc_metadata.get(key, [])
        if not observed:
            return False
        observed_set = set(observed)
        if not set(expected).issubset(observed_set):
            return False
    return True


def _document_reason(document: Document, filters: WatchlistFilters) -> list[str] | None:
    if not any([filters.keywords, filters.authors, filters.topics, filters.metadata]):
        return None
    if not _match_topics(document, filters):
        return None
    if not _match_authors(document, filters):
        return None
    if not _match_keywords(document, filters):
        return None
    if not _match_metadata(document, filters):
        return None
    reasons: list[str] = []
    if filters.topics:
        reasons.append("topic")
    if filters.authors:
        reasons.append("author")
    if filters.keywords:
        reasons.append("keyword")
    if filters.metadata:
        reasons.append("metadata")
    return reasons or ["recent"]


def _window_start(watchlist: UserWatchlist, now: datetime) -> datetime:
    if watchlist.last_run:
        return watchlist.last_run
    if watchlist.created_at:
        return watchlist.created_at
    return now - DEFAULT_LOOKBACK


def _collect_matches(
    session: Session, watchlist: UserWatchlist, filters: WatchlistFilters, now: datetime
) -> tuple[list[WatchlistMatch], datetime]:
    window_start = _window_start(watchlist, now)
    matches: list[WatchlistMatch] = []
    seen: set[tuple[str, str | None, str | None]] = set()

    documents = (
        session.execute(
            select(Document)
            .where(Document.created_at >= window_start)
            .order_by(Document.created_at.desc())
        )
        .scalars()
        .all()
    )
    for document in documents:
        reasons = _document_reason(document, filters)
        if reasons is None:
            continue
        snippet = document.abstract or document.title or None
        match = WatchlistMatch(
            document_id=document.id,
            snippet=snippet[:280] if snippet else None,
            reasons=reasons,
        )
        key = (match.document_id, match.passage_id, match.osis)
        if key not in seen:
            seen.add(key)
            matches.append(match)

    if filters.osis:
        rows = (
            session.execute(
                select(Passage)
                .join(Document, Passage.document_id == Document.id)
                .where(
                    Passage.osis_ref.in_(filters.osis),
                    Document.created_at >= window_start,
                )
            )
            .scalars()
            .all()
        )
        for passage in rows:
            snippet = passage.text or ""
            match = WatchlistMatch(
                document_id=passage.document_id,
                passage_id=passage.id,
                osis=passage.osis_ref,
                snippet=snippet[:280] if snippet else None,
                reasons=["osis"],
            )
            key = (match.document_id, match.passage_id, match.osis)
            if key not in seen:
                seen.add(key)
                matches.append(match)

    return matches, window_start


def list_watchlists(session: Session, user_id: str) -> list[WatchlistResponse]:
    rows = (
        session.execute(
            select(UserWatchlist)
            .where(UserWatchlist.user_id == user_id)
            .order_by(UserWatchlist.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [_watchlist_to_response(row) for row in rows]


def get_watchlist(session: Session, watchlist_id: str) -> UserWatchlist | None:
    return session.get(UserWatchlist, watchlist_id)


def create_watchlist(
    session: Session, user_id: str, payload: WatchlistCreateRequest
) -> WatchlistResponse:
    filters = payload.filters or WatchlistFilters()
    watchlist = UserWatchlist(
        user_id=user_id,
        name=payload.name,
        filters=filters.model_dump(mode="json"),
        cadence=payload.cadence,
        delivery_channels=_normalise_list(payload.delivery_channels),
        is_active=payload.is_active,
    )
    session.add(watchlist)
    session.commit()
    session.refresh(watchlist)
    return _watchlist_to_response(watchlist)


def update_watchlist(
    session: Session, watchlist: UserWatchlist, payload: WatchlistUpdateRequest
) -> WatchlistResponse:
    if payload.name is not None:
        watchlist.name = payload.name
    if payload.filters is not None:
        watchlist.filters = payload.filters.model_dump(mode="json")
    if payload.cadence is not None:
        watchlist.cadence = payload.cadence
    if payload.delivery_channels is not None:
        watchlist.delivery_channels = _normalise_list(payload.delivery_channels)
    if payload.is_active is not None:
        watchlist.is_active = payload.is_active
    session.add(watchlist)
    session.commit()
    session.refresh(watchlist)
    return _watchlist_to_response(watchlist)


def delete_watchlist(session: Session, watchlist: UserWatchlist) -> None:
    session.delete(watchlist)
    session.commit()


def _event_to_response(event: WatchlistEvent) -> WatchlistRunResponse:
    raw_matches = event.matches or []
    matches = [WatchlistMatch.model_validate(item) for item in raw_matches]
    return WatchlistRunResponse(
        id=event.id,
        watchlist_id=event.watchlist_id,
        run_started=event.run_started,
        run_completed=event.run_completed,
        window_start=event.window_start or event.run_started,
        matches=matches,
        document_ids=_normalise_list(event.document_ids),
        passage_ids=_normalise_list(event.passage_ids),
        delivery_status=event.delivery_status,
        error=event.error,
    )


def list_watchlist_events(
    session: Session,
    watchlist: UserWatchlist,
    *,
    since: datetime | None = None,
) -> list[WatchlistRunResponse]:
    stmt = (
        select(WatchlistEvent)
        .where(WatchlistEvent.watchlist_id == watchlist.id)
        .order_by(WatchlistEvent.run_started.desc())
    )
    if since is not None:
        stmt = stmt.where(WatchlistEvent.run_started >= since)
    rows = session.execute(stmt).scalars().all()
    return [_event_to_response(row) for row in rows]


def run_watchlist(
    session: Session,
    watchlist: UserWatchlist,
    *,
    persist: bool = True,
    now: datetime | None = None,
) -> WatchlistRunResponse:
    current_time = now or datetime.now(UTC)
    matches, window_start = _collect_matches(session, watchlist, _load_filters(watchlist.filters), current_time)
    run_started = current_time
    run_completed = datetime.now(UTC)
    document_ids = sorted({match.document_id for match in matches})
    passage_ids = sorted({match.passage_id for match in matches if match.passage_id})

    if persist:
        event = WatchlistEvent(
            watchlist_id=watchlist.id,
            run_started=run_started,
            run_completed=run_completed,
            window_start=window_start,
            matches=[match.model_dump(mode="json") for match in matches],
            document_ids=document_ids,
            passage_ids=passage_ids,
            delivery_status="pending",
        )
        watchlist.last_run = run_completed
        session.add(event)
        session.add(watchlist)
        session.commit()
        session.refresh(event)
        return _event_to_response(event)

    return WatchlistRunResponse(
        id=None,
        watchlist_id=watchlist.id,
        run_started=run_started,
        run_completed=run_completed,
        window_start=window_start,
        matches=matches,
        document_ids=document_ids,
        passage_ids=passage_ids,
        delivery_status="preview",
        error=None,
    )


def is_watchlist_due(watchlist: UserWatchlist, now: datetime | None = None) -> bool:
    if not watchlist.is_active:
        return False
    if watchlist.cadence == "manual":
        return False
    window = CADENCE_WINDOWS.get(watchlist.cadence, DEFAULT_LOOKBACK)
    reference = watchlist.last_run
    current = now or datetime.now(UTC)
    if reference is None:
        return True
    return reference <= current - window


def iter_due_watchlists(
    session: Session, now: datetime | None = None
) -> Iterable[UserWatchlist]:
    current = now or datetime.now(UTC)
    rows = (
        session.execute(select(UserWatchlist).where(UserWatchlist.is_active.is_(True)))
        .scalars()
        .all()
    )
    for watchlist in rows:
        if is_watchlist_due(watchlist, current):
            yield watchlist


__all__ = [
    "create_watchlist",
    "delete_watchlist",
    "get_watchlist",
    "is_watchlist_due",
    "iter_due_watchlists",
    "list_watchlist_events",
    "list_watchlists",
    "run_watchlist",
    "update_watchlist",
]
