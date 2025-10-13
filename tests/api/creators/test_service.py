import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.services.api.app.creators.service import (
    _average_confidence,
    _collect_quotes,
    _normalise_topic,
    _resolve_stance,
    fetch_creator_topic_profile,
    search_creators,
)
from theo.services.api.app.db.models import (
    Base,
    Creator,
    CreatorClaim,
    TranscriptQuote,
    TranscriptSegment,
    Video,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=
        [
            Creator.__table__,
            Video.__table__,
            TranscriptSegment.__table__,
            TranscriptQuote.__table__,
            CreatorClaim.__table__,
        ],
    )
    TestingSession = sessionmaker(bind=engine)
    with TestingSession() as session:
        yield session


def test_search_creators_trims_and_is_case_insensitive(session: Session) -> None:
    creators = [
        Creator(id="creator-1", name="Jane Doe"),
        Creator(id="creator-2", name="john smith"),
        Creator(id="creator-3", name="Janet Roe"),
    ]
    session.add_all(creators)
    session.commit()

    results = search_creators(session, query="  JANE  ", limit=5)

    assert [creator.name for creator in results] == ["Jane Doe", "Janet Roe"]


def test_normalise_topic_rejects_blank_values() -> None:
    with pytest.raises(ValueError):
        _normalise_topic("   ")


def test_resolve_stance_and_average_confidence() -> None:
    claims = [
        CreatorClaim(
            id="claim-1",
            topic="Topic",
            stance="Affirming",
            claim_md="c1",
            confidence=0.5,
        ),
        CreatorClaim(
            id="claim-2",
            topic="Topic",
            stance="affirming",
            claim_md="c2",
            confidence=None,
        ),
        CreatorClaim(
            id="claim-3",
            topic="Topic",
            stance="Neutral",
            claim_md="c3",
            confidence=0.2,
        ),
    ]

    assert _resolve_stance(claims) == "affirming"
    assert _average_confidence(claims) == pytest.approx((0.5 + 0.2) / 2)


def test_collect_quotes_deduplicates_orders_and_limits() -> None:
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    quote_late = TranscriptQuote(
        id="quote-1",
        quote_md="Quote late",
        salience=0.9,
        created_at=base_time + timedelta(hours=2),
    )
    quote_early = TranscriptQuote(
        id="quote-2",
        quote_md="Quote early",
        salience=0.9,
        created_at=base_time + timedelta(hours=1),
    )
    quote_low = TranscriptQuote(
        id="quote-3",
        quote_md="Quote low",
        salience=0.2,
        created_at=base_time + timedelta(hours=3),
    )
    segment_primary = TranscriptSegment(
        id="segment-1",
        text="Segment",
        quotes=[quote_late, quote_early, quote_low],
    )
    secondary_quote = TranscriptQuote(
        id="quote-4",
        quote_md="Secondary",
        salience=0.7,
        created_at=base_time + timedelta(hours=4),
    )
    segment_secondary = TranscriptSegment(
        id="segment-2",
        text="Segment 2",
        quotes=[secondary_quote],
    )
    claims = [
        CreatorClaim(
            id="claim-1",
            topic="Topic",
            claim_md="c1",
            segment=segment_primary,
        ),
        CreatorClaim(
            id="claim-2",
            topic="Topic",
            claim_md="c2",
            segment=segment_primary,
        ),
        CreatorClaim(
            id="claim-3",
            topic="Topic",
            claim_md="c3",
            segment=segment_secondary,
        ),
    ]

    quotes = _collect_quotes(claims, limit=2)

    assert [quote.id for quote in quotes] == ["quote-2", "quote-1"]


def test_fetch_creator_topic_profile_aggregates_claims(session: Session) -> None:
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    creator = Creator(id="creator-profile", name="Profiled Creator")
    video = Video(id="video-1", title="Video", creator=creator)

    segment_one = TranscriptSegment(id="segment-1", text="Segment one", video=video)
    segment_two = TranscriptSegment(id="segment-2", text="Segment two", video=video)

    quote_one = TranscriptQuote(
        id="quote-1",
        quote_md="Quote one",
        salience=0.9,
        created_at=base_time + timedelta(minutes=10),
        segment=segment_one,
        video=video,
    )
    quote_two = TranscriptQuote(
        id="quote-2",
        quote_md="Quote two",
        salience=0.6,
        created_at=base_time + timedelta(minutes=20),
        segment=segment_one,
        video=video,
    )
    quote_three = TranscriptQuote(
        id="quote-3",
        quote_md="Quote three",
        salience=0.95,
        created_at=base_time + timedelta(minutes=30),
        segment=segment_two,
        video=video,
    )

    claim_recent = CreatorClaim(
        id="claim-1",
        creator=creator,
        video=video,
        segment=segment_one,
        topic="Eschatology",
        stance="affirming",
        claim_md="recent",
        confidence=None,
        created_at=base_time + timedelta(days=2),
    )
    claim_middle = CreatorClaim(
        id="claim-2",
        creator=creator,
        video=video,
        segment=segment_one,
        topic="eschatology",
        stance="Affirming",
        claim_md="middle",
        confidence=0.5,
        created_at=base_time + timedelta(days=1),
    )
    claim_old = CreatorClaim(
        id="claim-3",
        creator=creator,
        video=video,
        segment=segment_two,
        topic="ESCHATOLOGY",
        stance="Opposing",
        claim_md="old",
        confidence=0.75,
        created_at=base_time,
    )
    irrelevant_claim = CreatorClaim(
        id="claim-4",
        creator=creator,
        video=video,
        segment=segment_two,
        topic="Other",
        stance="Neutral",
        claim_md="other",
        confidence=0.1,
    )

    session.add_all(
        [
            creator,
            video,
            segment_one,
            segment_two,
            quote_one,
            quote_two,
            quote_three,
            claim_recent,
            claim_middle,
            claim_old,
            irrelevant_claim,
        ]
    )
    session.commit()

    with pytest.raises(LookupError):
        fetch_creator_topic_profile(
            session, creator_id="missing", topic="Eschatology", limit=5
        )

    profile = fetch_creator_topic_profile(
        session,
        creator_id="creator-profile",
        topic="  Eschatology  ",
        limit=3,
    )

    assert profile.creator.id == "creator-profile"
    assert profile.topic == "Eschatology"
    assert profile.stance == "affirming"
    assert profile.confidence == pytest.approx((0.5 + 0.75) / 2)
    assert [quote.id for quote in profile.quotes] == ["quote-1", "quote-2", "quote-3"]
    assert {claim.id for claim in profile.claims} == {"claim-1", "claim-2", "claim-3"}
