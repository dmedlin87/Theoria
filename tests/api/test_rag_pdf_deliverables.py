from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from theo.infrastructure.api.app.ai.rag import (
    RAGAnswer,
    RAGCitation,
    SermonPrepResponse,
    build_sermon_deliverable,
    build_transcript_deliverable,
)
from theo.adapters.persistence.models import Document, Passage


def _sermon_response() -> SermonPrepResponse:
    citation = RAGCitation(
        index=1,
        osis="John.1.1",
        anchor="John 1:1",
        passage_id="passage-1",
        document_id="doc-1",
        snippet="In the beginning was the Word.",
        document_title="Gospel Commentary",
        source_url=None,
    )
    answer = RAGAnswer(
        summary="The sermon focuses on the eternal Word.",
        citations=[citation],
        model_name="test-model",
        model_output=None,
        guardrail_profile=None,
    )
    return SermonPrepResponse(
        topic="The Word",
        osis="John.1.1-5",
        outline=["Introduce the prologue", "Explore theological significance"],
        key_points=["Christ pre-exists", "Christ illuminates"],
        answer=answer,
    )


def test_build_sermon_deliverable_pdf_renders_binary() -> None:
    package = build_sermon_deliverable(_sermon_response(), formats=["pdf"])
    asset = package.get_asset("pdf")
    assert asset.filename == "sermon.pdf"
    assert asset.media_type == "application/pdf"
    assert isinstance(asset.content, (bytes, bytearray))
    assert asset.content.startswith(b"%PDF-")
    assert b"Sermon Prep" in asset.content


def test_build_transcript_deliverable_pdf_renders_binary() -> None:
    document = Document(id="doc-1", title="Interview with John")
    passage = Passage(
        id="passage-1",
        document_id="doc-1",
        text="Grace and truth were realised in Christ.",
        page_no=1,
        t_start=0.0,
        t_end=15.0,
        start_char=0,
        end_char=40,
        meta={"speaker": "Narrator"},
    )
    session = MagicMock(spec=Session)
    session.get.return_value = document
    query = MagicMock()
    session.query.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = [passage]

    package = build_transcript_deliverable(session, "doc-1", formats=["pdf"])
    asset = package.get_asset("pdf")
    assert asset.filename == "transcript.pdf"
    assert asset.media_type == "application/pdf"
    assert isinstance(asset.content, (bytes, bytearray))
    assert asset.content.startswith(b"%PDF-")
    assert b"Transcript" in asset.content
    assert b"Grace" in asset.content
