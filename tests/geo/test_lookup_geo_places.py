"""Tests for geographic lookup ranking and trigram acceleration."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from theo.services.api.app.core.database import Base
from theo.services.api.app.db.models import GeoModernLocation
from theo.services.api.app.research.geo import lookup_geo_places


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db_session = TestingSession()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _insert_sample_locations(session: Session) -> None:
    session.add_all(
        [
            GeoModernLocation(
                modern_id="bethlehem",
                friendly_id="Bethlehem",
                search_aliases=["Bethlehem Ephrathah"],
                names=None,
                geom_kind="point",
                confidence=0.95,
                longitude=35.2,
                latitude=31.7,
                raw={"coordinates_source": {"name": "Test"}},
            ),
            GeoModernLocation(
                modern_id="bethany",
                friendly_id="Bethany",
                search_aliases=["Bethany Beyond the Jordan"],
                names=[{"name": "Bethany"}],
                geom_kind="point",
                confidence=0.75,
                longitude=34.9,
                latitude=31.8,
                raw={},
            ),
            GeoModernLocation(
                modern_id="jerusalem",
                friendly_id="Jerusalem",
                search_aliases=["Yerushalayim"],
                names=[{"name": "Yerushalayim"}],
                geom_kind="point",
                confidence=0.99,
                longitude=35.2,
                latitude=31.8,
                raw={},
            ),
        ]
    )
    session.commit()


def test_lookup_geo_places_python_fallback_orders_results(session: Session) -> None:
    _insert_sample_locations(session)

    results = lookup_geo_places(session, query="beth", limit=2)

    assert [item.modern_id for item in results] == ["bethlehem", "bethany"]
    assert results[0].aliases == ["Bethlehem Ephrathah"]
    assert len(results) == 2


@pytest.mark.integration
def test_lookup_geo_places_postgres_trigram_matches() -> None:
    database_url = os.environ.get("TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("TEST_POSTGRES_URL not configured")

    pytest.importorskip("psycopg")

    engine = create_engine(database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with engine.connect() as connection:
        connection.execution_options(isolation_level="AUTOCOMMIT").execute(
            text("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        )

    with Session(engine) as session:
        _insert_sample_locations(session)

        results = lookup_geo_places(session, query="beth", limit=2)

        assert [item.modern_id for item in results] == ["bethlehem", "bethany"]

    engine.dispose()
