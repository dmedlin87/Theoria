"""Routes for managing AI digest watchlists."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...ai.watchlists_service import WatchlistNotFoundError, WatchlistsService
from ...core.database import get_session
from ...models.watchlists import (
    WatchlistCreateRequest,
    WatchlistResponse,
    WatchlistRunResponse,
    WatchlistUpdateRequest,
)


router = APIRouter(prefix="/digest/watchlists")


def _service(session: Session) -> WatchlistsService:
    return WatchlistsService(session)


@router.get("", response_model=list[WatchlistResponse])
def list_user_watchlists(
    user_id: str = Query(..., description="Owning user identifier"),
    session: Session = Depends(get_session),
) -> list[WatchlistResponse]:
    return _service(session).list(user_id)


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_user_watchlist(
    payload: WatchlistCreateRequest, session: Session = Depends(get_session)
) -> WatchlistResponse:
    return _service(session).create(payload)


@router.patch("/{watchlist_id}", response_model=WatchlistResponse)
def update_user_watchlist(
    watchlist_id: str,
    payload: WatchlistUpdateRequest,
    session: Session = Depends(get_session),
) -> WatchlistResponse:
    try:
        return _service(session).update(watchlist_id, payload)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_watchlist(
    watchlist_id: str, session: Session = Depends(get_session)
) -> None:
    try:
        _service(session).delete(watchlist_id)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc


@router.get("/{watchlist_id}/events", response_model=list[WatchlistRunResponse])
def list_user_watchlist_events(
    watchlist_id: str,
    since: datetime | None = Query(
        default=None, description="Return events generated after this timestamp"
    ),
    session: Session = Depends(get_session),
) -> list[WatchlistRunResponse]:
    try:
        return _service(session).list_events(watchlist_id, since=since)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc


@router.get("/{watchlist_id}/preview", response_model=WatchlistRunResponse)
def preview_user_watchlist(
    watchlist_id: str, session: Session = Depends(get_session)
) -> WatchlistRunResponse:
    try:
        return _service(session).preview(watchlist_id)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc


@router.post("/{watchlist_id}/run", response_model=WatchlistRunResponse)
def run_user_watchlist(
    watchlist_id: str, session: Session = Depends(get_session)
) -> WatchlistRunResponse:
    try:
        return _service(session).run(watchlist_id)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc

