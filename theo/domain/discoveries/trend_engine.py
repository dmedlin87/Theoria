"""Trend analysis engine comparing topic distributions across snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping, Sequence

from .models import CorpusSnapshotSummary


@dataclass(frozen=True)
class TrendDiscovery:
    """Represents an emerging or declining topic trend within the corpus."""

    title: str
    description: str
    confidence: float
    relevance_score: float
    metadata: Mapping[str, object] = field(default_factory=dict)


class TrendDiscoveryEngine:
    """Compare corpus snapshots to surface significant topic trends."""

    def __init__(
        self,
        *,
        min_snapshots: int = 3,
        history_window: int = 5,
        max_trends: int = 3,
        min_percent_change: float = 10.0,
    ) -> None:
        self.min_snapshots = max(3, int(min_snapshots))
        self.history_window = max(self.min_snapshots, int(history_window))
        self.max_trends = max(1, int(max_trends))
        self.min_percent_change = max(0.0, float(min_percent_change))

    def detect(
        self, snapshots: Sequence[CorpusSnapshotSummary]
    ) -> list[TrendDiscovery]:
        """Detect trending topics across *snapshots* ordered by time."""

        if len(snapshots) < self.min_snapshots:
            return []

        ordered = sorted(snapshots, key=lambda snap: snap.snapshot_date)
        if len(ordered) > self.history_window:
            ordered = ordered[-self.history_window :]
        if len(ordered) < self.min_snapshots:
            return []

        distributions: list[dict[str, float]] = []
        labels: dict[str, str] = {}
        for snapshot in ordered:
            dist, label_map = self._extract_distribution(snapshot)
            distributions.append(dist)
            for key, value in label_map.items():
                labels.setdefault(key, value)

        if not any(distribution for distribution in distributions):
            return []

        topics = sorted({topic for dist in distributions for topic in dist})
        if not topics:
            return []

        start_date = ordered[0].snapshot_date
        end_date = ordered[-1].snapshot_date
        timeframe = self._format_timeframe(start_date, end_date)
        trend_candidates: list[tuple[float, TrendDiscovery]] = []

        for topic in topics:
            series = [dist.get(topic, 0.0) for dist in distributions]
            if not any(series):
                continue
            baseline = sum(series[:-1]) / max(len(series[:-1]), 1)
            latest = series[-1]
            if baseline == latest == 0.0:
                continue
            change_fraction = latest - baseline
            if baseline == 0.0 and latest > 0.0:
                percent_change = round(latest * 100, 2)
            else:
                percent_change = round((change_fraction / baseline) * 100, 2)
            if abs(percent_change) < self.min_percent_change:
                continue

            history = [
                {
                    "date": snapshot.snapshot_date.astimezone(UTC).isoformat(),
                    "share": round(value * 100, 2),
                }
                for snapshot, value in zip(ordered, series, strict=False)
            ]
            display_topic = labels.get(topic, topic.title())
            direction = "rising" if percent_change > 0 else "declining"
            title = f"{display_topic!s} trend {direction}"
            start_share = round(series[0] * 100, 2)
            end_share = round(latest * 100, 2)
            description = (
                f"The emphasis on {display_topic!s} has {direction} over the analyzed period. "
                f"It changed from {start_share:.2f}% to {end_share:.2f}% between {timeframe}."
            )
            magnitude = min(abs(percent_change) / 100.0, 1.0)
            confidence = round(0.55 + 0.4 * magnitude, 4)
            relevance = round(0.4 + 0.5 * magnitude, 4)
            trend_metadata: dict[str, object] = {
                "relatedTopics": [display_topic],
                "trendData": {
                    "topic": display_topic,
                    "change": percent_change,
                    "timeframe": timeframe,
                    "direction": "up" if percent_change > 0 else "down",
                    "history": history,
                },
            }
            trend = TrendDiscovery(
                title=title,
                description=description,
                confidence=min(confidence, 0.99),
                relevance_score=min(relevance, 0.99),
                metadata=trend_metadata,
            )
            trend_candidates.append((abs(percent_change), trend))

        trend_candidates.sort(key=lambda item: item[0], reverse=True)
        return [trend for _, trend in trend_candidates[: self.max_trends]]

    def _extract_distribution(
        self, snapshot: CorpusSnapshotSummary
    ) -> tuple[dict[str, float], dict[str, str]]:
        raw_values: dict[str, float] = {}
        label_map: dict[str, str] = {}
        metadata = snapshot.metadata or {}
        dominant = snapshot.dominant_themes or {}

        for key in ("topic_distribution", "topic_counts", "topic_frequencies"):
            candidate = metadata.get(key)
            if isinstance(candidate, Mapping):
                for topic, value in candidate.items():
                    normalised_topic = self._normalise_topic(topic)
                    if not normalised_topic:
                        continue
                    amount = self._coerce_float(value)
                    if amount <= 0.0:
                        continue
                    raw_values[normalised_topic] = raw_values.get(normalised_topic, 0.0) + amount
                    label_map.setdefault(normalised_topic, str(topic))
                if raw_values:
                    break

        if not raw_values:
            top_topics = []
            if isinstance(dominant, Mapping):
                candidate = dominant.get("top_topics") or dominant.get("topTopics")
                if isinstance(candidate, Sequence):
                    top_topics = [topic for topic in candidate if isinstance(topic, str)]
            if not top_topics and isinstance(metadata, Mapping):
                fallback = metadata.get("top_topics") or metadata.get("topTopics")
                if isinstance(fallback, Sequence):
                    top_topics = [topic for topic in fallback if isinstance(topic, str)]
            for topic in top_topics:
                normalised_topic = self._normalise_topic(topic)
                if not normalised_topic:
                    continue
                raw_values[normalised_topic] = raw_values.get(normalised_topic, 0.0) + 1.0
                label_map.setdefault(normalised_topic, topic)

        total = sum(raw_values.values())
        if total <= 0.0:
            return {}, label_map
        distribution = {
            topic: value / total for topic, value in raw_values.items() if value > 0.0
        }
        return distribution, label_map

    @staticmethod
    def _coerce_float(value: object) -> float:
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        if number != number or number in (float("inf"), float("-inf")):
            return 0.0
        return float(max(number, 0.0))

    @staticmethod
    def _normalise_topic(topic: object) -> str:
        if not isinstance(topic, str):
            return ""
        normalised = topic.strip().lower()
        return normalised

    @staticmethod
    def _format_timeframe(start: datetime, end: datetime) -> str:
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        if start.date() == end.date():
            return start.strftime("%d %b %Y")
        if start.year == end.year:
            if start.month == end.month:
                return f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
            return f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
        return f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"


__all__ = ["TrendDiscovery", "TrendDiscoveryEngine"]
