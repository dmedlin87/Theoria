from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.infrastructure.api.app.ai.rag import (  # noqa: E402
    CollaborationResponse,
    ComparativeAnalysisResponse,
    CorpusCurationReport,
    DevotionalResponse,
    MultimediaDigestResponse,
    RAGAnswer,
    SermonPrepResponse,
    VerseCopilotResponse,
)
from theo.infrastructure.api.app.models.ai import (  # noqa: E402
    CollaborationRequest,
    ComparativeAnalysisRequest,
    CorpusCurationRequest,
    DevotionalRequest,
    MultimediaDigestRequest,
    SermonPrepRequest,
    VerseCopilotRequest,
)
from theo.infrastructure.api.app.models.search import HybridSearchFilters  # noqa: E402
from theo.infrastructure.api.app.routes.ai.workflows import flows as flows_module  # noqa: E402


class DummyRecorder:
    def __init__(self) -> None:
        self.finalised_payload: Any | None = None

    def finalize(self, *, final_md: str | None, output_payload: Any) -> None:  # noqa: D401
        self.finalised_payload = {
            "final_md": final_md,
            "output_payload": output_payload,
        }


class DummyTrailService:
    def __init__(self, _: Any) -> None:
        return

    @contextmanager
    def start_trail(self, *args: Any, **kwargs: Any) -> Iterator[DummyRecorder]:
        _ = args, kwargs
        recorder = DummyRecorder()
        yield recorder


@pytest.fixture(autouse=True)
def patch_trail_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flows_module, "TrailService", DummyTrailService)


def _answer(summary: str) -> RAGAnswer:
    return RAGAnswer(summary=summary, citations=[])


def _identity(response: Any) -> Callable[..., Any]:
    def _call(*_: Any, **__: Any) -> Any:
        return response

    return _call


@pytest.mark.parametrize(
    "func_name,request_obj,response_obj,patch_name",
    [
        (
            "verse_copilot",
            VerseCopilotRequest(osis="John.1.1"),
            VerseCopilotResponse(
                osis="John.1.1",
                question="Who is the Word?",
                answer=_answer("In the beginning was the Word."),
                follow_ups=["Explore related passages"],
            ),
            "generate_verse_brief",
        ),
        (
            "sermon_prep",
            SermonPrepRequest(topic="Hope", osis="John.1", filters=HybridSearchFilters()),
            SermonPrepResponse(
                topic="Hope",
                osis="John.1",
                outline=["Opening", "Body", "Closing"],
                key_points=["Focus on the light"],
                answer=_answer("Outline prepared."),
            ),
            "generate_sermon_prep_outline",
        ),
        (
            "devotional_flow",
            DevotionalRequest(osis="Psalm.23", focus="comfort"),
            DevotionalResponse(
                osis="Psalm.23",
                focus="comfort",
                reflection="The Lord is my shepherd.",
                prayer="Guide us.",
                answer=_answer("Reflection complete."),
            ),
            "generate_devotional_flow",
        ),
        (
            "collaboration",
            CollaborationRequest(
                thread="thread-1",
                osis="John.17",
                viewpoints=["Scholar", "Pastor"],
            ),
            CollaborationResponse(
                thread="thread-1",
                synthesized_view="Unified perspective.",
                answer=_answer("Collaboration synthesized."),
            ),
            "run_research_reconciliation",
        ),
        (
            "corpus_curation",
            CorpusCurationRequest(),
            CorpusCurationReport(
                since=datetime.now(timezone.utc),
                documents_processed=1,
                summaries=["Document summary"],
            ),
            "run_corpus_curation",
        ),
        (
            "comparative_analysis",
            ComparativeAnalysisRequest(osis="John.1", participants=["A", "B"]),
            ComparativeAnalysisResponse(
                osis="John.1",
                participants=["A", "B"],
                comparisons=["A focuses on Logos", "B emphasizes creation"],
                answer=_answer("Comparison complete."),
            ),
            "generate_comparative_analysis",
        ),
        (
            "multimedia_digest",
            MultimediaDigestRequest(collection="weekly"),
            MultimediaDigestResponse(
                collection="weekly",
                highlights=["Video summary"],
                answer=_answer("Digest prepared."),
            ),
            "generate_multimedia_digest",
        ),
    ],
)
def test_workflow_routes_return_models(
    monkeypatch: pytest.MonkeyPatch,
    func_name: str,
    request_obj: Any,
    response_obj: Any,
    patch_name: str,
) -> None:
    monkeypatch.setattr(
        flows_module,
        patch_name,
        _identity(response_obj),
    )
    workflow = getattr(flows_module, func_name)
    result = workflow(request_obj, session=object())
    assert result is response_obj
