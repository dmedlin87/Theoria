"""Public API for guardrailed RAG workflows."""

from __future__ import annotations

import sys
import types

from . import guardrails as _guardrails_module
from . import workflow as _workflow_module
from .guardrails import GuardrailError, ensure_completion_safe
from ...telemetry import instrument_workflow
from ..registry import get_llm_registry
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
from .workflow import (
    REFUSAL_MESSAGE,
    REFUSAL_MODEL_NAME,
    _build_citations,
    _validate_model_completion,
    build_guardrail_refusal,
    build_sermon_deliverable,
    build_sermon_prep_package,
    build_transcript_deliverable,
    build_transcript_package,
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
    generate_verse_brief,
    run_corpus_curation,
    run_guarded_chat,
    run_research_reconciliation,
    _record_used_citation_feedback,
    _guarded_answer,
    _search,
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
    "_build_citations",
    "_validate_model_completion",
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
    "_record_used_citation_feedback",
    "_guarded_answer",
    "_search",
]


class _RAGModule(types.ModuleType):
    """Module proxy that keeps workflow exports patchable for tests."""

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(_workflow_module, name):
            setattr(_workflow_module, name, value)
        if hasattr(_guardrails_module, name):
            setattr(_guardrails_module, name, value)
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _RAGModule
