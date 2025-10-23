"""Aggregations that surface creator perspectives for specific verses."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from theo.services.api.app.persistence_models import (
    Creator,
    CreatorClaim,
    CreatorVerseRollup,
    TranscriptQuote,
    TranscriptQuoteVerse,
    TranscriptSegment,
    TranscriptSegmentVerse,
    Video,
)

from ..ingest.osis import expand_osis_reference, osis_intersects
from ..models.creators import (
    CreatorVersePerspectiveCreator,
    CreatorVersePerspectiveMeta,
    CreatorVersePerspectiveResponse,
    VersePerspectiveQuote,
    VersePerspectiveVideo,
)


@dataclass(slots=True)
class _CreatorAggregate:
    creator: Creator
    claims: list[CreatorClaim] = field(default_factory=list)
    stance_counts: Counter[str] = field(default_factory=Counter)
    confidences: list[float] = field(default_factory=list)
    quotes: dict[str, TranscriptQuote] = field(default_factory=dict)


class CreatorVersePerspectiveService:
    """Build and cache creator verse rollups."""

    MAX_STORED_QUOTES = 10

    def __init__(self, session: Session):
        self._session = session

    # Cache maintenance -------------------------------------------------------
    def refresh_many(self, osis_refs: Iterable[str]) -> None:
        """Rebuild cached rollups for the provided OSIS references."""

        unique_refs = sorted({ref.strip() for ref in osis_refs if ref})
        for reference in unique_refs:
            self._rebuild_rollups(reference)

    # Public API -----------------------------------------------------------------
    def get_perspectives(
        self,
        osis: str,
        *,
        limit_creators: int,
        limit_quotes: int,
    ) -> CreatorVersePerspectiveResponse:
        """Return cached or freshly built perspective data for *osis*."""

        rollups = self._load_rollups(osis)
        if not rollups:
            rollups = self._rebuild_rollups(osis)

        creators = self._build_creators_payload(
            rollups, limit_creators=limit_creators, limit_quotes=limit_quotes
        )
        generated_at = self._resolve_generated_at(rollups)

        return CreatorVersePerspectiveResponse(
            osis=osis,
            total_creators=len(rollups),
            creators=creators,
            meta=CreatorVersePerspectiveMeta(range=osis, generated_at=generated_at),
        )

    # Internal helpers -----------------------------------------------------------
    def _load_rollups(self, osis: str) -> list[CreatorVerseRollup]:
        stmt = (
            select(CreatorVerseRollup)
            .where(CreatorVerseRollup.osis == osis)
            .options(joinedload(CreatorVerseRollup.creator))
            .order_by(
                CreatorVerseRollup.claim_count.desc(),
                CreatorVerseRollup.creator_id.asc(),
            )
        )
        return list(self._session.scalars(stmt))

    def _rebuild_rollups(self, osis: str) -> list[CreatorVerseRollup]:
        aggregates = self._collect_claims(osis)

        # Remove stale cache entries before inserting fresh rollups.
        (
            self._session.query(CreatorVerseRollup)
            .filter(CreatorVerseRollup.osis == osis)
            .delete(synchronize_session=False)
        )

        timestamp = datetime.now(UTC)
        for aggregate in aggregates.values():
            if not aggregate.claims:
                continue
            top_quotes = self._rank_quotes(aggregate.quotes.values())
            rollup = CreatorVerseRollup(
                osis=osis,
                creator_id=aggregate.creator.id,
                stance_counts=dict(aggregate.stance_counts) or None,
                avg_confidence=self._average_confidence(aggregate.confidences),
                claim_count=len(aggregate.claims),
                top_quote_ids=[quote.id for quote in top_quotes],
                generated_at=timestamp,
            )
            self._session.add(rollup)

        self._session.commit()
        return self._load_rollups(osis)

    def _collect_claims(self, osis: str) -> dict[str, _CreatorAggregate]:
        verse_ids = sorted(expand_osis_reference(osis))
        if not verse_ids:
            return self._collect_claims_fallback(osis)

        stmt = (
            select(CreatorClaim)
            .join(CreatorClaim.segment)
            .join(TranscriptSegmentVerse)
            .where(TranscriptSegmentVerse.verse_id.in_(verse_ids))
            .options(
                joinedload(CreatorClaim.creator),
                joinedload(CreatorClaim.segment).joinedload(TranscriptSegment.video),
            )
        )

        claims = list(self._session.scalars(stmt).unique())
        if not claims:
            return {}

        segment_ids = {
            claim.segment_id for claim in claims if getattr(claim, "segment_id", None)
        }
        quotes_by_segment: dict[str, list[TranscriptQuote]] = {}
        if segment_ids:
            quote_stmt = (
                select(TranscriptQuote)
                .join(TranscriptQuoteVerse)
                .where(TranscriptQuote.segment_id.in_(segment_ids))
                .where(TranscriptQuoteVerse.verse_id.in_(verse_ids))
                .options(
                    joinedload(TranscriptQuote.video),
                    joinedload(TranscriptQuote.segment).joinedload(
                        TranscriptSegment.video
                    ),
                )
            )
            for quote in self._session.scalars(quote_stmt).unique():
                if quote.segment_id:
                    quotes_by_segment.setdefault(quote.segment_id, []).append(quote)

        aggregates: dict[str, _CreatorAggregate] = {}
        for claim in claims:
            creator = claim.creator
            segment = claim.segment
            if creator is None or segment is None:
                continue

            aggregate = aggregates.setdefault(
                creator.id,
                _CreatorAggregate(creator=creator),
            )
            aggregate.claims.append(claim)
            if claim.stance:
                aggregate.stance_counts[claim.stance.lower()] += 1
            if claim.confidence is not None:
                aggregate.confidences.append(float(claim.confidence))

            for quote in quotes_by_segment.get(segment.id, []):
                aggregate.quotes.setdefault(quote.id, quote)

        return aggregates

    def _collect_claims_fallback(self, osis: str) -> dict[str, _CreatorAggregate]:
        stmt = (
            select(CreatorClaim)
            .options(
                joinedload(CreatorClaim.creator),
                joinedload(CreatorClaim.segment)
                .joinedload(TranscriptSegment.quotes)
                .joinedload(TranscriptQuote.video),
                joinedload(CreatorClaim.segment).joinedload(TranscriptSegment.video),
            )
            .where(CreatorClaim.segment_id.isnot(None))
        )
        aggregates: dict[str, _CreatorAggregate] = {}
        for claim in self._session.scalars(stmt).unique():
            creator = claim.creator
            segment = claim.segment
            if creator is None or segment is None or not segment.osis_refs:
                continue
            if not self._segment_matches(segment, osis):
                continue

            aggregate = aggregates.setdefault(
                creator.id,
                _CreatorAggregate(creator=creator),
            )
            aggregate.claims.append(claim)
            if claim.stance:
                aggregate.stance_counts[claim.stance.lower()] += 1
            if claim.confidence is not None:
                aggregate.confidences.append(float(claim.confidence))

            for quote in segment.quotes:
                if quote.osis_refs and self._quote_matches(quote, osis):
                    aggregate.quotes.setdefault(quote.id, quote)

        return aggregates

    def _segment_matches(self, segment: TranscriptSegment, osis: str) -> bool:
        return any(osis_intersects(reference, osis) for reference in segment.osis_refs or [])

    def _quote_matches(self, quote: TranscriptQuote, osis: str) -> bool:
        return any(osis_intersects(reference, osis) for reference in quote.osis_refs or [])

    def _rank_quotes(
        self, quotes: Iterable[TranscriptQuote]
    ) -> list[TranscriptQuote]:
        def _sort_key(quote: TranscriptQuote) -> tuple[float, datetime]:
            salience_key = -(quote.salience or 0.0)
            created_at = quote.created_at
            if created_at is None:
                normalised = datetime.min.replace(tzinfo=UTC)
            elif created_at.tzinfo is None:
                normalised = created_at.replace(tzinfo=UTC)
            else:
                normalised = created_at
            return salience_key, normalised

        ordered = sorted(quotes, key=_sort_key)
        return ordered[: self.MAX_STORED_QUOTES]

    def _average_confidence(self, values: Iterable[float]) -> float | None:
        values_list = [value for value in values if value is not None]
        if not values_list:
            return None
        return float(sum(values_list) / len(values_list))

    def _build_creators_payload(
        self,
        rollups: list[CreatorVerseRollup],
        *,
        limit_creators: int,
        limit_quotes: int,
    ) -> list[CreatorVersePerspectiveCreator]:
        if not rollups:
            return []

        quote_ids: set[str] = set()
        for rollup in rollups:
            quote_ids.update(rollup.top_quote_ids or [])

        quotes_map: dict[str, TranscriptQuote] = {}
        if quote_ids:
            quote_stmt = (
                select(TranscriptQuote)
                .where(TranscriptQuote.id.in_(quote_ids))
                .options(
                    joinedload(TranscriptQuote.video),
                    joinedload(TranscriptQuote.segment).joinedload(
                        TranscriptSegment.video
                    ),
                )
            )
            quotes_map = {quote.id: quote for quote in self._session.scalars(quote_stmt)}

        creators: list[CreatorVersePerspectiveCreator] = []
        for rollup in rollups[:limit_creators]:
            creator = rollup.creator
            stance_distribution_map = self._normalize_stance_counts(rollup.stance_counts)
            stance_distribution = stance_distribution_map or None
            stance = None
            if stance_distribution:
                stance = max(
                    stance_distribution.items(),
                    key=lambda item: (item[1], item[0]),
                )[0]

            quotes = self._build_quote_payload(
                rollup.top_quote_ids or [], quotes_map, limit_quotes
            )
            creators.append(
                CreatorVersePerspectiveCreator(
                    creator_id=creator.id,
                    creator_name=creator.name,
                    stance=stance,
                    confidence=rollup.avg_confidence,
                    claim_count=rollup.claim_count,
                    stance_distribution=stance_distribution,
                    quotes=quotes,
                )
            )

        return creators

    def _normalize_stance_counts(
        self, stance_counts: dict | list | None
    ) -> dict[str, int]:
        if not stance_counts:
            return {}

        if isinstance(stance_counts, Mapping):
            items = stance_counts.items()
        elif isinstance(stance_counts, Sequence) and not isinstance(
            stance_counts, (str, bytes)
        ):
            items = stance_counts
        else:
            return {}

        normalized: dict[str, int] = {}
        for entry in items:
            if isinstance(entry, Sequence) and not isinstance(entry, (str, bytes)) and len(entry) == 2:
                key, value = entry
            else:
                continue
            try:
                normalized[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return normalized

    def _build_quote_payload(
        self,
        quote_ids: list[str],
        quotes_map: dict[str, TranscriptQuote],
        limit_quotes: int,
    ) -> list[VersePerspectiveQuote]:
        payload: list[VersePerspectiveQuote] = []
        for quote_id in quote_ids[:limit_quotes]:
            quote = quotes_map.get(quote_id)
            if quote is None:
                continue
            video = self._resolve_video(quote)
            payload.append(
                VersePerspectiveQuote(
                    segment_id=quote.segment_id,
                    quote_md=quote.quote_md,
                    source_ref=quote.source_ref,
                    osis_refs=quote.osis_refs,
                    video=(
                        VersePerspectiveVideo(
                            video_id=video.video_id if video else None,
                            title=video.title if video else None,
                            url=video.url if video else None,
                            t_start=quote.segment.t_start if quote.segment else None,
                        )
                        if video
                        else None
                    ),
                )
            )
        return payload

    def _resolve_video(self, quote: TranscriptQuote) -> Video | None:
        if quote.video:
            return quote.video
        if quote.segment and quote.segment.video:
            return quote.segment.video
        return None

    def _resolve_generated_at(
        self, rollups: list[CreatorVerseRollup]
    ) -> datetime:
        if not rollups:
            return datetime.now(UTC)
        return max(rollup.generated_at for rollup in rollups if rollup.generated_at)

