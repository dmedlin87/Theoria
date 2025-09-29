"""Routes for managing AI digest watchlists."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ...ai.watchlists_service import WatchlistNotFoundError, WatchlistsService
from ...core.database import get_session
from ...models.watchlists import (
    WatchlistCreateRequest,
    WatchlistResponse,
    WatchlistRunResponse,
    WatchlistUpdateRequest,
)
from ...security import Principal, require_principal


_WATCHLIST_NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Watchlist not found"}
}


router = APIRouter(prefix="/digest/watchlists")


def _service(session: Session) -> WatchlistsService:
    return WatchlistsService(session)


def _require_user_subject(principal: Principal) -> str:
    subject = principal.get("subject")
    if not subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return subject


@router.get("", response_model=list[WatchlistResponse])
def list_user_watchlists(
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> list[WatchlistResponse]:
    user_id = _require_user_subject(principal)
    return _service(session).list(user_id)


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_user_watchlist(
    payload: WatchlistCreateRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> WatchlistResponse:
    user_id = _require_user_subject(principal)
    return _service(session).create(user_id, payload)


@router.patch(
    "/{watchlist_id}",
    response_model=WatchlistResponse,
    responses=_WATCHLIST_NOT_FOUND_RESPONSE,
)
def update_user_watchlist(
    watchlist_id: str,
    payload: WatchlistUpdateRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> WatchlistResponse:
    try:
        user_id = _require_user_subject(principal)
        return _service(session).update(watchlist_id, payload, user_id)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc


@router.delete(
    "/{watchlist_id}",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_WATCHLIST_NOT_FOUND_RESPONSE,
)
def delete_user_watchlist(
    watchlist_id: str,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> Response:
    try:
        user_id = _require_user_subject(principal)
        _service(session).delete(watchlist_id, user_id)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{watchlist_id}/events",
    response_model=list[WatchlistRunResponse],
    responses=_WATCHLIST_NOT_FOUND_RESPONSE,
)
def list_user_watchlist_events(
    watchlist_id: str,
    since: datetime | None = Query(
        default=None, description="Return events generated after this timestamp"
    ),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> list[WatchlistRunResponse]:
    try:
        user_id = _require_user_subject(principal)
        return _service(session).list_events(watchlist_id, user_id, since=since)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc


@router.get(
    "/{watchlist_id}/preview",
    response_model=WatchlistRunResponse,
    responses=_WATCHLIST_NOT_FOUND_RESPONSE,
)
def preview_user_watchlist(
    watchlist_id: str,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> WatchlistRunResponse:
    try:
        user_id = _require_user_subject(principal)
        return _service(session).preview(watchlist_id, user_id)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc


@router.post(
    "/{watchlist_id}/run",
    response_model=WatchlistRunResponse,
    responses=_WATCHLIST_NOT_FOUND_RESPONSE,
)
def run_user_watchlist(
    watchlist_id: str,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> WatchlistRunResponse:
    try:
        user_id = _require_user_subject(principal)
        return _service(session).run(watchlist_id, user_id)
    except WatchlistNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Watchlist not found") from exc

