"""Public API for guardrailed RAG workflows."""

from __future__ import annotations

import sys
import types

from ...telemetry import instrument_workflow
from ..registry import get_llm_registry
from . import (
    chat as _chat_module,
    collaboration as _collaboration_module,
    corpus as _corpus_module,
    deliverables as _deliverables_module,
    guardrail_helpers as _guardrail_helpers_module,
    guardrails as _guardrails_module,
    refusals as _refusals_module,
    retrieval as _retrieval_module,
    verse as _verse_module,
    workflow as _workflow_module,
)
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


class _RAGModule(types.ModuleType):
    """Module proxy that keeps workflow exports patchable for tests."""

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(_chat_module, name):
            setattr(_chat_module, name, value)
        if hasattr(_workflow_module, name):
            setattr(_workflow_module, name, value)
        if hasattr(_deliverables_module, name):
            setattr(_deliverables_module, name, value)
        if hasattr(_guardrails_module, name):
            setattr(_guardrails_module, name, value)
        if hasattr(_guardrail_helpers_module, name):
            setattr(_guardrail_helpers_module, name, value)
        if hasattr(_refusals_module, name):
            setattr(_refusals_module, name, value)
        if hasattr(_retrieval_module, name):
            setattr(_retrieval_module, name, value)
        if hasattr(_collaboration_module, name):
            setattr(_collaboration_module, name, value)
        if hasattr(_corpus_module, name):
            setattr(_corpus_module, name, value)
        if hasattr(_verse_module, name):
            setattr(_verse_module, name, value)
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _RAGModule
