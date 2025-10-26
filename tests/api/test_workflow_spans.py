from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.orm import Session

from theo.services.api.app.ai import rag


def _patch_instrumentation(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, object]]]:
    spans: list[tuple[str, dict[str, object]]] = []

    @contextmanager
    def _instrument(name: str, **attributes: object):
        spans.append((name, attributes))
        yield MagicMock()

    monkeypatch.setattr(rag, "instrument_workflow", _instrument)
    return spans


def _patch_feedback_recorder(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple, dict]]:
    calls: list[tuple[tuple, dict]] = []

    def _capture(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(rag, "record_used_citation_feedback", _capture)
    return calls


def test_multimedia_digest_emits_span_and_records_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    spans = _patch_instrumentation(monkeypatch)
    feedback_calls = _patch_feedback_recorder(monkeypatch)

    fake_result = SimpleNamespace(
        id="multimedia-1",
        osis_ref="Ps.1.1",
        document_id="doc-1",
        snippet="Sample snippet",
        score=0.9,
    )
    fake_answer = rag.RAGAnswer(
        summary="Audio-visual insights",
        citations=[
            rag.RAGCitation(
                index=1,
                osis="Ps.1.1",
                anchor="v1",
                passage_id="passage-1",
                document_id="doc-1",
                document_title="Sample",
                snippet="Blessed is the one",
            )
        ],
        model_name="dummy",
        model_output="output",
    )

    monkeypatch.setattr(rag, "search_passages", lambda *_, **__: [fake_result])
    monkeypatch.setattr(rag, "get_llm_registry", lambda session: MagicMock())
    monkeypatch.setattr(
        rag, "_guarded_answer_or_refusal", lambda *_, **__: fake_answer, raising=False
    )

    session = MagicMock(spec=Session)
    recorder = MagicMock()

    response = rag.generate_multimedia_digest(
        session,
        collection="recent",
        model_name="dummy",
        recorder=recorder,
    )

    assert response.answer == fake_answer
    assert spans and spans[0][0] == "multimedia_digest"
    recorder.log_step.assert_called_once()
    recorder.record_citations.assert_called_once_with(fake_answer.citations)
    assert len(feedback_calls) == 1


def test_devotional_flow_emits_span(monkeypatch: pytest.MonkeyPatch) -> None:
    spans = _patch_instrumentation(monkeypatch)
    feedback_calls = _patch_feedback_recorder(monkeypatch)

    fake_result = SimpleNamespace(
        id="devotional-1",
        osis_ref="John.1.1",
        document_id="doc-2",
        snippet="In the beginning",
        score=0.8,
    )
    fake_answer = rag.RAGAnswer(
        summary="Reflective summary",
        citations=[
            rag.RAGCitation(
                index=1,
                osis="John.1.1",
                anchor="v1",
                passage_id="passage-2",
                document_id="doc-2",
                document_title="Gospel of John",
                snippet="In the beginning was the Word",
            )
        ],
    )

    monkeypatch.setattr(rag, "search_passages", lambda *_, **__: [fake_result])
    monkeypatch.setattr(rag, "get_llm_registry", lambda session: MagicMock())
    monkeypatch.setattr(
        rag, "_guarded_answer_or_refusal", lambda *_, **__: fake_answer, raising=False
    )

    session = MagicMock(spec=Session)
    recorder = MagicMock()

    response = rag.generate_devotional_flow(
        session,
        osis="John.1.1",
        focus="grace",
        model_name="dummy",
        recorder=recorder,
    )

    assert response.answer == fake_answer
    assert spans and spans[0][0] == "devotional"
    recorder.log_step.assert_called_once()
    recorder.record_citations.assert_called_once_with(fake_answer.citations)
    assert len(feedback_calls) == 1


def test_research_reconciliation_emits_span(monkeypatch: pytest.MonkeyPatch) -> None:
    spans = _patch_instrumentation(monkeypatch)
    feedback_calls = _patch_feedback_recorder(monkeypatch)

    fake_result = SimpleNamespace(
        id="collab-1",
        osis_ref="Acts.2.1",
        document_id="doc-3",
        snippet="Pentecost",
        score=0.7,
    )
    fake_answer = rag.RAGAnswer(
        summary="Synthesised view",
        citations=[
            rag.RAGCitation(
                index=1,
                osis="Acts.2.1",
                anchor="v1",
                passage_id="passage-3",
                document_id="doc-3",
                document_title="Acts",
                snippet="When the day of Pentecost came",
            )
        ],
    )

    monkeypatch.setattr(rag, "search_passages", lambda *_, **__: [fake_result])
    monkeypatch.setattr(rag, "get_llm_registry", lambda session: MagicMock())
    monkeypatch.setattr(
        rag, "_guarded_answer_or_refusal", lambda *_, **__: fake_answer, raising=False
    )

    session = MagicMock(spec=Session)
    recorder = MagicMock()

    response = rag.run_research_reconciliation(
        session,
        thread="pentecost",
        osis="Acts.2",
        viewpoints=["historical", "charismatic"],
        model_name="dummy",
        recorder=recorder,
    )

    assert response.answer == fake_answer
    assert spans and spans[0][0] == "research_reconciliation"
    recorder.log_step.assert_called_once()
    recorder.record_citations.assert_called_once_with(fake_answer.citations)
    assert len(feedback_calls) == 1


def test_corpus_curation_emits_span(monkeypatch: pytest.MonkeyPatch) -> None:
    spans = _patch_instrumentation(monkeypatch)

    session = MagicMock(spec=Session)
    execution = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    execution.scalars.return_value = scalars
    session.execute.return_value = execution

    recorder = MagicMock()

    response = rag.run_corpus_curation(
        session,
        since=None,
        recorder=recorder,
    )

    assert response.documents_processed == 0
    assert spans and spans[0][0] == "corpus_curation"
    recorder.log_step.assert_called_once()
