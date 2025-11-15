"""Public API for guardrailed RAG workflows with optional dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - prefer importing the full implementation
    from . import chat as _chat_module
    from . import collaboration as _collaboration_module
    from . import corpus as _corpus_module
    from . import deliverables as _deliverables_module
    from . import guardrail_helpers as _guardrail_helpers_module
    from . import guardrails as _guardrails_module
    from . import refusals as _refusals_module
    from . import retrieval as _retrieval_module
    from . import verse as _verse_module
    from . import workflow as _workflow_module

    from theo.application.facades.telemetry import instrument_workflow
    from ..registry import get_llm_registry
    from .deliverables import (
        generate_comparative_analysis,
        generate_devotional_flow,
        generate_multimedia_digest,
        generate_sermon_prep_outline,
    )
    from .guardrail_helpers import (
        GuardrailError,
        build_citations,
        ensure_completion_safe,
        validate_model_completion,
    )
    from .models import (
        CollaborationResponse,
        ComparativeAnalysisResponse,
        CorpusCurationReport,
        DevotionalResponse,
        MultimediaDigestResponse,
        RAGAnswer,
        RAGCitation,
        SermonPrepResponse,
        VerseCopilotResponse,
    )
    from .retrieval import record_used_citation_feedback, search_passages
    from .verse import generate_verse_brief
    from .corpus import run_corpus_curation
    from .collaboration import run_research_reconciliation
    from .chat import (
        REFUSAL_MESSAGE,
        REFUSAL_MODEL_NAME,
        _guarded_answer,
        build_guardrail_refusal,
        build_sermon_deliverable,
        build_sermon_prep_package,
        build_transcript_deliverable,
        build_transcript_package,
        run_guarded_chat,
    )

    __all__ = [
        "CollaborationResponse",
        "ComparativeAnalysisResponse",
        "CorpusCurationReport",
        "DevotionalResponse",
        "GuardrailError",
        "MultimediaDigestResponse",
        "RAGAnswer",
        "RAGCitation",
        "REFUSAL_MESSAGE",
        "REFUSAL_MODEL_NAME",
        "_guarded_answer",
        "build_citations",
        "validate_model_completion",
        "ensure_completion_safe",
        "SermonPrepResponse",
        "VerseCopilotResponse",
        "build_guardrail_refusal",
        "build_sermon_deliverable",
        "build_sermon_prep_package",
        "build_transcript_deliverable",
        "build_transcript_package",
        "generate_comparative_analysis",
        "generate_devotional_flow",
        "generate_multimedia_digest",
        "generate_sermon_prep_outline",
        "generate_verse_brief",
        "get_llm_registry",
        "instrument_workflow",
        "run_corpus_curation",
        "run_guarded_chat",
        "run_research_reconciliation",
        "record_used_citation_feedback",
        "search_passages",
    ]

    import sys
    import types

    class _RAGModule(types.ModuleType):
        """Module proxy that keeps workflow exports patchable for tests."""

        def __setattr__(self, name: str, value: object) -> None:
            for candidate in (
                _chat_module,
                _workflow_module,
                _deliverables_module,
                _guardrails_module,
                _guardrail_helpers_module,
                _refusals_module,
                _retrieval_module,
                _collaboration_module,
                _corpus_module,
                _verse_module,
            ):
                if candidate is _workflow_module:
                    candidate.__dict__[name] = value
                    continue
                if hasattr(candidate, name):
                    setattr(candidate, name, value)
            super().__setattr__(name, value)

    sys.modules[__name__].__class__ = _RAGModule

except ModuleNotFoundError as exc:  # pragma: no cover - lightweight fallback
    _IMPORT_ERROR = exc

    from pydantic import BaseModel

    class RAGCitation(BaseModel):
        index: int
        osis: str
        anchor: str
        passage_id: str | None = None
        document_id: str | None = None
        document_title: str | None = None
        snippet: str | None = None
        source_url: str | None = None

    __all__ = ["RAGCitation"]

    try:  # pragma: no cover - ensure forward refs resolve when models import this module
        from ..models.ai import ChatMemoryEntry
    except Exception:  # pragma: no cover - cyclic import guard
        ChatMemoryEntry = None
    else:
        try:
            ChatMemoryEntry.model_rebuild()
        except Exception:
            pass

    def __getattr__(name: str) -> Any:  # pragma: no cover - exercised in tests
        if name in __all__:
            return globals()[name]
        raise ModuleNotFoundError(
            "Optional AI dependencies are not installed; "
            "only RAGCitation is available in the lightweight fallback."
        ) from _IMPORT_ERROR
