from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[6]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.orm import Session

from theo.application.facades import database as database_module
from theo.application.facades.database import Base, configure_engine, get_engine
from theo.services.api.app.persistence_models import Document, Passage
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.models.verses import VerseMentionsFilters
from theo.services.api.app.retriever.verses import get_mentions_for_osis


@contextmanager
def _session():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "filters.db"
        configure_engine(f"sqlite:///{db_path}")
        engine = get_engine()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as session:
                yield session
        finally:
            engine.dispose()
            database_module._engine = None  # type: ignore[attr-defined]
            database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_mentions_filters_respect_author_and_collection() -> None:
    with _session() as session:
        matching_doc = Document(
            id="doc-match",
            title="Match",
            source_type="pdf",
            collection="series",
            authors=["Author A"],
        )
        other_collection = Document(
            id="doc-other-collection",
            title="Other Collection",
            source_type="pdf",
            collection="other",
            authors=["Author A"],
        )
        other_author = Document(
            id="doc-other-author",
            title="Other Author",
            source_type="pdf",
            collection="series",
            authors=["Author B"],
        )
        session.add_all([matching_doc, other_collection, other_author])
        session.flush()

        verse_ids = sorted(expand_osis_reference("John.3.16"))
        start_id, end_id = verse_ids[0], verse_ids[-1]

        session.add_all(
            [
                Passage(
                    id="passage-match",
                    document_id=matching_doc.id,
                    text="Match",
                    osis_ref="John.3.16",
                    osis_verse_ids=verse_ids,
                    osis_start_verse_id=start_id,
                    osis_end_verse_id=end_id,
                ),
                Passage(
                    id="passage-other-collection",
                    document_id=other_collection.id,
                    text="Other collection",
                    osis_ref="John.3.16",
                    osis_verse_ids=verse_ids,
                    osis_start_verse_id=start_id,
                    osis_end_verse_id=end_id,
                ),
                Passage(
                    id="passage-other-author",
                    document_id=other_author.id,
                    text="Other author",
                    osis_ref="John.3.16",
                    osis_verse_ids=verse_ids,
                    osis_start_verse_id=start_id,
                    osis_end_verse_id=end_id,
                ),
            ]
        )
        session.commit()

        mentions = get_mentions_for_osis(
            session=session,
            osis="John.3.16",
            filters=VerseMentionsFilters(collection="series", author="Author A"),
        )

    assert [mention.passage.document_id for mention in mentions] == ["doc-match"]
