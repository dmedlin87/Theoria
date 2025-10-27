"""Pydantic schemas for personalised watchlists and alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import APIModel


class WatchlistFilters(APIModel):
    """Structured filter definition reused across watchlists."""

    osis: list[str] | None = None
    keywords: list[str] | None = None
    authors: list[str] | None = None
    topics: list[str] | None = None
    metadata: dict[str, Any] | None = None


class WatchlistMatch(APIModel):
    """Individual match surfaced during a watchlist evaluation run."""

    document_id: str
    passage_id: str | None = None
    osis: str | None = None
    snippet: str | None = None
    reasons: list[str] | None = None


class WatchlistResponse(APIModel):
    """Serialized representation of a stored user watchlist."""

    id: str
    user_id: str
    name: str
    filters: WatchlistFilters
    cadence: str
    delivery_channels: list[str]
    is_active: bool
    last_run: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WatchlistCreateRequest(APIModel):
    """Payload required to create a new watchlist."""

    name: str
    filters: WatchlistFilters | None = None
    cadence: str = "daily"
    delivery_channels: list[str] | None = None
    is_active: bool = True


class WatchlistUpdateRequest(APIModel):
    """Patch payload for updating an existing watchlist."""

    name: str | None = None
    filters: WatchlistFilters | None = None
    cadence: str | None = None
    delivery_channels: list[str] | None = None
    is_active: bool | None = None


class WatchlistRunResponse(APIModel):
    """Response returned when a watchlist is evaluated."""

    id: str | None = None
    watchlist_id: str
    run_started: datetime
    run_completed: datetime
    window_start: datetime
    matches: list[WatchlistMatch]
    document_ids: list[str]
    passage_ids: list[str]
    delivery_status: str | None = None
    error: str | None = None


__all__ = [
    "WatchlistFilters",
    "WatchlistMatch",
    "WatchlistResponse",
    "WatchlistCreateRequest",
    "WatchlistUpdateRequest",
    "WatchlistRunResponse",
]
