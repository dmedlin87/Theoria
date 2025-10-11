from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sys

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core import database as database_module  # noqa: E402
from theo.services.api.app.core.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
)
from theo.services.api.app.db.models import (  # noqa: E402
    Document,
    Passage,
    PassageVerse,
)
from theo.services.api.app.ingest.osis import expand_osis_reference  # noqa: E402
from theo.services.api.app.models.verses import VerseMentionsFilters  # noqa: E402
from theo.services.api.app.retriever.verses import get_mentions_for_osis  # noqa: E402


def _prepare_engine(tmp_path: Path):
    configure_engine(f"sqlite:///{tmp_path / 'verses.db'}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def _seeded_session(tmp_path: Path):
    engine = _prepare_engine(tmp_path)
    try:
        with Session(engine) as session:
            documents = [
                Document(
                    id="doc-1",
                    title="First",
                    source_type="pdf",
                    collection="Alpha",
                    authors=["Alice"],
                ),
                Document(
                    id="doc-2",
                    title="Second",
                    source_type="pdf",
                    collection="Beta",
                    authors=["Bob"],
                ),
                Document(
                    id="doc-3",
                    title="Third",
                    source_type="html",
                    collection="Alpha",
                    authors=["Alice"],
                ),
            ]
            session.add_all(documents)
            session.flush()

            passages = [
                Passage(id="p-1", document_id="doc-1", text="Ref 1", osis_ref="John.3.16"),
                Passage(id="p-2", document_id="doc-2", text="Ref 2", osis_ref="John.3.16"),
                Passage(id="p-3", document_id="doc-3", text="Ref 3", osis_ref="John.3.17"),
            ]
            session.add_all(passages)
            session.flush()

            for passage, reference in zip(
                passages,
                ["John.3.16", "John.3.16", "John.3.17"],
            ):
                for verse_id in expand_osis_reference(reference):
                    session.add(PassageVerse(passage_id=passage.id, verse_id=verse_id))

            session.commit()
            yield session
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_get_mentions_for_osis_returns_matching_passages(tmp_path: Path) -> None:
    with _seeded_session(tmp_path) as session:
        mentions = get_mentions_for_osis(session, osis="John.3.16")

    assert [mention.passage.document_id for mention in mentions] == ["doc-1", "doc-2"]
    assert {mention.passage.id for mention in mentions} == {"p-1", "p-2"}
    assert all(mention.context_snippet for mention in mentions)


def test_get_mentions_for_osis_respects_filters(tmp_path: Path) -> None:
    with _seeded_session(tmp_path) as session:
        collection_filtered = get_mentions_for_osis(
            session,
            osis="John.3.16",
            filters=VerseMentionsFilters(collection="Alpha"),
        )
        author_filtered = get_mentions_for_osis(
            session,
            osis="John.3.16",
            filters=VerseMentionsFilters(author="Bob"),
        )
        source_filtered = get_mentions_for_osis(
            session,
            osis="John.3.16",
            filters=VerseMentionsFilters(source_type="html"),
        )

    assert [mention.passage.document_id for mention in collection_filtered] == ["doc-1"]
    assert [mention.passage.document_id for mention in author_filtered] == ["doc-2"]
    assert source_filtered == []
