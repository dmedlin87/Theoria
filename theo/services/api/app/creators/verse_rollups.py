"""Aggregation helpers for verse-level creator perspectives."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from ..db.models import (
    Creator,
    CreatorClaim,
    CreatorVerseRollup,
    TranscriptQuote,
    TranscriptSegment,
)

_MAX_STORED_QUOTES = 10


@dataclass(slots=True)
class VersePerspectiveQuoteData:
    """Container for the hydrated quote used in the response."""

    quote: TranscriptQuote


@dataclass(slots=True)
class VersePerspectiveCreatorData:
    """Aggregated perspective data for a creator."""

    creator: Creator
    stance_counts: dict[str, int]
    stance: str | None
    avg_confidence: float | None
    claim_count: int
    quotes: list[VersePerspectiveQuoteData]


@dataclass(slots=True)
class VersePerspectiveSummaryData:
    """Summary payload for a verse-level perspective query."""

    osis: str
    range: str
    creators: list[VersePerspectiveCreatorData]
    generated_at: datetime
    total_creators: int


def _normalise_osis(osis: str) -> str:
    cleaned = osis.strip()
    if not cleaned:
        raise ValueError("osis cannot be blank")
    return cleaned


def _segment_matches(segment: TranscriptSegment | None, osis: str) -> bool:
    if segment is None:
        return False
    if segment.primary_osis == osis:
        return True
    if segment.osis_refs and osis in segment.osis_refs:
        return True
    return False


def _stance_summary(claims: Iterable[CreatorClaim]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for claim in claims:
        if claim.stance:
            counts[claim.stance.lower()] += 1
    return counts


def _average_confidence(claims: Iterable[CreatorClaim]) -> float | None:
    confidences = [claim.confidence for claim in claims if claim.confidence is not None]
    if not confidences:
        return None
    return float(sum(confidences) / len(confidences))


def _collect_quotes(claims: Iterable[CreatorClaim]) -> list[TranscriptQuote]:
    quotes: list[TranscriptQuote] = []
    seen: set[str] = set()
    for claim in claims:
        segment = claim.segment
        if segment is None:
            continue
        ordered = sorted(
            segment.quotes,
            key=lambda quote: (
                -(quote.salience or 0.0),
                quote.created_at,
                quote.id,
            ),
        )
        for quote in ordered:
            if quote.id in seen:
                continue
            quotes.append(quote)
            seen.add(quote.id)
    return quotes


def _resolve_top_stance(stance_counts: dict[str, int]) -> str | None:
    if not stance_counts:
        return None
    sorted_items = sorted(
        stance_counts.items(), key=lambda item: (-item[1], item[0].lower())
    )
    return sorted_items[0][0]


class CreatorVersePerspectiveService:
    """Service object for building and retrieving verse-level perspectives."""

    def __init__(self, session: Session, *, max_stored_quotes: int = _MAX_STORED_QUOTES) -> None:
        self.session = session
        self.max_stored_quotes = max_stored_quotes

    def _load_rollups(self, osis: str) -> list[CreatorVerseRollup]:
        return (
            self.session.query(CreatorVerseRollup)
            .options(joinedload(CreatorVerseRollup.creator))
            .filter(CreatorVerseRollup.osis == osis)
            .order_by(CreatorVerseRollup.claim_count.desc(), CreatorVerseRollup.creator_id.asc())
            .all()
        )

    def rebuild_rollups(self, osis: str) -> list[CreatorVerseRollup]:
        osis_value = _normalise_osis(osis)
        (
            self.session.query(CreatorVerseRollup)
            .filter(CreatorVerseRollup.osis == osis_value)
            .delete(synchronize_session=False)
        )

        claims = (
            self.session.query(CreatorClaim)
            .options(
                joinedload(CreatorClaim.creator),
                joinedload(CreatorClaim.segment).joinedload(TranscriptSegment.quotes),
            )
            .join(TranscriptSegment, CreatorClaim.segment)
            .filter(
                or_(
                    TranscriptSegment.primary_osis == osis_value,
                    TranscriptSegment.osis_refs.is_not(None),
                )
            )
            .all()
        )

        grouped: dict[str, list[CreatorClaim]] = defaultdict(list)
        for claim in claims:
            if claim.creator is None or claim.creator_id is None:
                continue
            if not _segment_matches(claim.segment, osis_value):
                continue
            grouped[claim.creator_id].append(claim)

        rollups: list[CreatorVerseRollup] = []
        now = datetime.now(UTC)
        for creator_id, creator_claims in grouped.items():
            creator = creator_claims[0].creator
            stance_counts = _stance_summary(creator_claims)
            quotes = _collect_quotes(creator_claims)
            rollup = CreatorVerseRollup(
                osis=osis_value,
                creator_id=creator_id,
                claim_count=len(creator_claims),
                stance_counts=dict(stance_counts),
                avg_confidence=_average_confidence(creator_claims),
                top_quote_ids=[quote.id for quote in quotes[: self.max_stored_quotes]],
                generated_at=now,
            )
            rollup.creator = creator
            self.session.add(rollup)
            rollups.append(rollup)

        self.session.commit()
        return self._load_rollups(osis_value)

    def get_summary(
        self,
        osis: str,
        *,
        limit_creators: int,
        limit_quotes: int,
    ) -> VersePerspectiveSummaryData:
        osis_value = _normalise_osis(osis)
        rollups = self._load_rollups(osis_value)
        if not rollups:
            rollups = self.rebuild_rollups(osis_value)

        if not rollups:
            return VersePerspectiveSummaryData(
                osis=osis_value,
                range=osis_value,
                creators=[],
                generated_at=datetime.now(UTC),
                total_creators=0,
            )

        selected_rollups = rollups[:limit_creators]
        total_creators = len(rollups)

        quote_ids: set[str] = set()
        for rollup in selected_rollups:
            if rollup.top_quote_ids:
                quote_ids.update(rollup.top_quote_ids[:limit_quotes])

        quotes_by_id: dict[str, TranscriptQuote] = {}
        if quote_ids:
            quotes = (
                self.session.query(TranscriptQuote)
                .options(
                    selectinload(TranscriptQuote.video),
                    selectinload(TranscriptQuote.segment).selectinload(TranscriptSegment.video),
                )
                .filter(TranscriptQuote.id.in_(quote_ids))
                .all()
            )
            quotes_by_id = {quote.id: quote for quote in quotes}

        creators: list[VersePerspectiveCreatorData] = []
        for rollup in selected_rollups:
            creator = rollup.creator
            stance_counts = rollup.stance_counts or {}
            quotes: list[VersePerspectiveQuoteData] = []
            if rollup.top_quote_ids:
                for quote_id in rollup.top_quote_ids[:limit_quotes]:
                    quote = quotes_by_id.get(quote_id)
                    if quote is None:
                        continue
                    quotes.append(VersePerspectiveQuoteData(quote=quote))

            creators.append(
                VersePerspectiveCreatorData(
                    creator=creator,
                    stance_counts=stance_counts,
                    stance=_resolve_top_stance(stance_counts),
                    avg_confidence=rollup.avg_confidence,
                    claim_count=rollup.claim_count,
                    quotes=quotes,
                )
            )

        generated_at = max((rollup.generated_at for rollup in rollups), default=datetime.now(UTC))
        return VersePerspectiveSummaryData(
            osis=osis_value,
            range=osis_value,
            creators=creators,
            generated_at=generated_at,
            total_creators=total_creators,
        )
