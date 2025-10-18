"""High level helpers for managing AI watchlists."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..analytics.watchlists import (
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    list_watchlist_events,
    list_watchlists,
    run_watchlist,
    update_watchlist,
)
from theo.services.api.app.persistence_models import UserWatchlist
from ..models.watchlists import (
    WatchlistCreateRequest,
    WatchlistResponse,
    WatchlistRunResponse,
    WatchlistUpdateRequest,
)


class WatchlistNotFoundError(LookupError):
    """Raised when the requested watchlist does not exist."""


class WatchlistsService:
    """Wrap watchlist persistence operations for API routers."""

    def __init__(self, session: Session):
        self._session = session

    def list(self, user_id: str) -> list[WatchlistResponse]:
        return list_watchlists(self._session, user_id)

    def create(self, user_id: str, payload: WatchlistCreateRequest) -> WatchlistResponse:
        return create_watchlist(self._session, user_id, payload)

    def update(
        self, watchlist_id: str, payload: WatchlistUpdateRequest, user_id: str
    ) -> WatchlistResponse:
        watchlist = self._require_watchlist(watchlist_id, user_id)
        return update_watchlist(self._session, watchlist, payload)

    def delete(self, watchlist_id: str, user_id: str) -> None:
        watchlist = self._require_watchlist(watchlist_id, user_id)
        delete_watchlist(self._session, watchlist)

    def list_events(
        self,
        watchlist_id: str,
        user_id: str,
        *,
        since: datetime | None = None,
    ) -> list[WatchlistRunResponse]:
        watchlist = self._require_watchlist(watchlist_id, user_id)
        return list_watchlist_events(self._session, watchlist, since=since)

    def preview(self, watchlist_id: str, user_id: str) -> WatchlistRunResponse:
        watchlist = self._require_watchlist(watchlist_id, user_id)
        return run_watchlist(self._session, watchlist, persist=False)

    def run(self, watchlist_id: str, user_id: str) -> WatchlistRunResponse:
        watchlist = self._require_watchlist(watchlist_id, user_id)
        return run_watchlist(self._session, watchlist, persist=True)

    def _require_watchlist(self, watchlist_id: str, user_id: str) -> UserWatchlist:
        watchlist = get_watchlist(self._session, watchlist_id)
        if watchlist is None or watchlist.user_id != user_id:
            raise WatchlistNotFoundError(watchlist_id)
        return watchlist

