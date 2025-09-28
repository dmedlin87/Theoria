from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
)
from theo.services.api.app.db.models import Document, Passage  # noqa: E402
from theo.services.api.app.ingest.tei_pipeline import (  # noqa: E402
    HTRResult,
    ingest_pilot_corpus,
)
from theo.services.api.app.models.search import HybridSearchRequest  # noqa: E402
from theo.services.api.app.retriever.hybrid import hybrid_search  # noqa: E402


def _prepare_database(tmp_path: Path) -> None:
    db_path = tmp_path / "tei_pipeline.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


class DummyHTRClient:
    """Fixture-friendly OCR client returning deterministic output."""

    def __init__(self, confidence: float = 0.94) -> None:
        self.confidence = confidence

    def transcribe(self, path: Path):
        text = path.read_text("utf-8")
        yield HTRResult(text=text, confidence=self.confidence, page_no=1)


def test_ingest_pilot_corpus_emits_tei_metadata(tmp_path) -> None:
    _prepare_database(tmp_path)
    engine = get_engine()

    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    sermon_page = corpus_dir / "page1.txt"
    sermon_page.write_text(
        (
            "Athanasius: The faithful in Alexandria confess the Logos.\n"
            "Deacon Peter: Remember John 1:1 when resisting Arius."
        ),
        encoding="utf-8",
    )

    client = DummyHTRClient(confidence=0.91)

    with Session(engine) as session:
        document = ingest_pilot_corpus(
            session,
            corpus_dir,
            htr_client=client,
            document_metadata={"title": "Patristic Volume", "authors": ["Athanasius"]},
        )
        document_id = document.id
        session.commit()

    with Session(engine) as session:
        stored = session.get(Document, document_id)
        assert stored is not None
        passages = session.query(Passage).filter_by(document_id=document_id).all()

    assert passages, "expected TEI pipeline to create passages"
    first = passages[0]
    assert first.tei_xml is not None and "<TEI" in first.tei_xml
    assert first.meta is not None
    assert first.meta.get("ocr_confidence") == pytest.approx(0.91, rel=1e-3)
    assert first.meta.get("tei")
    assert "Athanasius" in first.meta["tei"]["persons"]
    assert "Alexandria" in first.meta["tei"]["places"]
    assert any(ref.startswith("John.") for ref in first.meta["tei"]["scripture"])

    with Session(engine) as session:
        request = HybridSearchRequest(query="Alexandria", k=5)
        results = hybrid_search(session, request)

    assert results, "hybrid search should surface TEI-aware passages"
    result_meta = results[0].meta
    assert result_meta is not None and "tei" in result_meta
    tei_meta = result_meta["tei"]
    assert "Alexandria" in tei_meta["places"]
    assert "Athanasius" in tei_meta["persons"]
