from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from theo.domain.discoveries.models import CorpusSnapshotSummary
from theo.domain.discoveries.trend_engine import TrendDiscoveryEngine


@pytest.fixture
def snapshot_dates() -> list[datetime]:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    return [base + timedelta(days=30 * idx) for idx in range(3)]


def _build_snapshot(
    date: datetime,
    *,
    distribution: dict[str, float] | None = None,
    dominant_topics: list[str] | None = None,
) -> CorpusSnapshotSummary:
    metadata: dict[str, object] = {}
    if distribution is not None:
        metadata["topic_distribution"] = distribution
    dominant = {"top_topics": dominant_topics or []}
    return CorpusSnapshotSummary(
        snapshot_date=date,
        document_count=10,
        dominant_themes=dominant,
        metadata=metadata,
    )


def test_trend_engine_detects_rising_topic(snapshot_dates: list[datetime]) -> None:
    engine = TrendDiscoveryEngine(min_percent_change=5.0, max_trends=3)
    snapshots = [
        _build_snapshot(snapshot_dates[0], distribution={"faith": 2, "hope": 8}),
        _build_snapshot(snapshot_dates[1], distribution={"faith": 5, "hope": 5}),
        _build_snapshot(snapshot_dates[2], distribution={"faith": 9, "hope": 3}),
    ]

    results = engine.detect(snapshots)

    assert results
    trend = next((item for item in results if "faith" in item.title.lower()), None)
    assert trend is not None
    assert "faith" in trend.title.lower()
    assert trend.metadata["trendData"]["change"] > 0
    assert trend.metadata["trendData"]["timeframe"]
    history = trend.metadata["trendData"]["history"]
    assert isinstance(history, list) and len(history) == 3
    assert history[-1]["share"] > history[0]["share"]


def test_trend_engine_requires_minimum_snapshots(snapshot_dates: list[datetime]) -> None:
    engine = TrendDiscoveryEngine()
    snapshots = [
        _build_snapshot(snapshot_dates[0], distribution={"faith": 3, "hope": 7}),
        _build_snapshot(snapshot_dates[1], distribution={"faith": 4, "hope": 6}),
    ]

    assert engine.detect(snapshots) == []


def test_trend_engine_handles_mixed_inputs(snapshot_dates: list[datetime]) -> None:
    engine = TrendDiscoveryEngine(min_percent_change=5.0, max_trends=2)
    snapshots = [
        _build_snapshot(snapshot_dates[0], dominant_topics=["Mercy", "Faith"]),
        _build_snapshot(snapshot_dates[1], distribution={"mercy": 8, "justice": 2}),
        _build_snapshot(snapshot_dates[2], distribution={"mercy": 1, "justice": 9}),
    ]

    results = engine.detect(snapshots)

    assert results  # At least one trend detected
    decline = next((trend for trend in results if "mercy" in trend.title.lower()), None)
    assert decline is not None
    assert decline.metadata["trendData"]["change"] < 0
    assert decline.metadata["trendData"]["direction"] == "down"
    assert len(decline.metadata["trendData"]["history"]) == 3
