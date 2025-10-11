from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker

from theo.services.api.app.core.database import Base
from theo.services.api.app.db.models import GeoModernLocation
from theo.services.api.app.research.geo import lookup_geo_places


class DummyResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class DummySession:
    def __init__(self, rows):
        self._rows = rows
        self.statements = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def execute(self, statement, *_args, **_kwargs):
        self.statements.append(statement)
        return DummyResult(self._rows)

    def query(self, *_args, **_kwargs):  # pragma: no cover - guard fallback
        pytest.fail("lookup_geo_places should not use ORM query in Postgres mode")


@pytest.fixture()
def sqlite_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'geo.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_lookup_geo_places_postgres_similarity_uses_single_bounded_query():
    bethlehem = GeoModernLocation(
        modern_id="bethlehem",
        friendly_id="Bethlehem",
        search_terms="bethlehem bethlehem ephrathah",
        confidence=0.95,
        names=[{"name": "Bethlehem"}, {"name": "Bethlehem Ephrathah"}],
        raw={"coordinates_source": {"name": "Sample"}},
    )
    bethel = GeoModernLocation(
        modern_id="bethel",
        friendly_id="Bethel",
        search_terms="bethel",
        confidence=0.7,
        names=[{"name": "Bethel"}],
        raw={"coordinates_source": {"name": "Sample"}},
    )

    dummy = DummySession([(bethlehem, 0.9), (bethel, 0.6)])

    items = lookup_geo_places(dummy, query="beth", limit=2)

    assert dummy.statements, "lookup_geo_places should execute a statement"
    assert len(dummy.statements) == 1

    compiled = dummy.statements[0].compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    assert "LIMIT 2" in str(compiled)
    assert [item.modern_id for item in items] == ["bethlehem", "bethel"]


def test_lookup_geo_places_sqlite_fallback_preserves_ordering(sqlite_session: Session):
    sqlite_session.add_all(
        [
            GeoModernLocation(
                modern_id="bethlehem",
                friendly_id="Bethlehem",
                search_terms="bethlehem bethlehem ephrathah",
                confidence=0.95,
                latitude=31.7054,
                longitude=35.2003,
                names=[{"name": "Bethlehem"}, {"name": "Bethlehem Ephrathah"}],
                raw={"coordinates_source": {"name": "Sample"}},
            ),
            GeoModernLocation(
                modern_id="bethany",
                friendly_id="Bethany",
                search_terms="bethany bethany beyond the jordan",
                confidence=0.85,
                latitude=31.7714,
                longitude=35.2137,
                names=[{"name": "Bethany"}, "Bethany Beyond the Jordan"],
                raw={"coordinates_source": {"name": "Sample"}},
            ),
            GeoModernLocation(
                modern_id="capernaum",
                friendly_id="Capernaum",
                search_terms="capernaum",
                confidence=0.6,
                latitude=32.8803,
                longitude=35.5733,
                names=[{"name": "Capernaum"}],
                raw={"coordinates_source": {"name": "Sample"}},
            ),
        ]
    )
    sqlite_session.commit()

    items = lookup_geo_places(sqlite_session, query="beth", limit=2)

    assert [item.modern_id for item in items] == ["bethlehem", "bethany"]
    assert items[0].aliases == ["Bethlehem Ephrathah"]
    assert len(items) == 2
