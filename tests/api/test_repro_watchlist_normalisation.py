"""Regression reproduction tests for watchlist normalisation helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from theo.infrastructure.api.app.analytics import watchlists
from theo.adapters.persistence.models import WatchlistEvent


def test_repro_watchlist_normalises_none_entries() -> None:
    """WatchlistEvent responses should omit null identifiers."""

    event = WatchlistEvent(
        id="event-1",
        watchlist_id="watchlist-1",
        run_started=datetime.now(UTC),
        run_completed=datetime.now(UTC),
        window_start=datetime.now(UTC),
        matches=None,
        document_ids=["doc-1", None],
        passage_ids=[None, "passage-1"],
    )

    response = watchlists._event_to_response(event)

    assert response.document_ids == ["doc-1"]
    assert response.passage_ids == ["passage-1"]
