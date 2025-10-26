"""Compatibility surface for guardrailed RAG workflows."""

from __future__ import annotations

import sys
import types
from typing import Any

from . import chat as _chat_module
from . import collaboration as _collaboration_module
from . import corpus as _corpus_module
from . import deliverables as _deliverables_module
from . import telemetry as _telemetry_module
from . import verse as _verse_module
from .collaboration import run_research_reconciliation
from .corpus import run_corpus_curation
from .deliverables import (
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
)
from .exports import (
    build_sermon_deliverable,
    build_sermon_prep_package,
    build_transcript_deliverable,
    build_transcript_package,
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
from .refusals import REFUSAL_MESSAGE, REFUSAL_MODEL_NAME, build_guardrail_refusal
from .retrieval import record_used_citation_feedback, search_passages
from .verse import generate_verse_brief


def _propagate_log_workflow_event(callback: Any) -> None:
    """Ensure guardrail modules share the same workflow logging hook."""

    _telemetry_module.log_workflow_event = callback
    _deliverables_module.log_workflow_event = callback
    _collaboration_module.log_workflow_event = callback
    _corpus_module.log_workflow_event = callback
    _verse_module.log_workflow_event = callback
    # ``cache`` also logs workflow events (e.g., cache hits/misses).
    # Import lazily to avoid circular imports during module initialisation.
    from . import cache as _cache_module  # noqa: WPS433  (local import for dependency cycle)

    _cache_module.log_workflow_event = callback


log_workflow_event = _telemetry_module.log_workflow_event
_propagate_log_workflow_event(log_workflow_event)

_chat_module.configure_deliverable_hooks(
    _chat_module.DeliverableHooks(
        generate_sermon_prep_outline=generate_sermon_prep_outline,
        generate_comparative_analysis=generate_comparative_analysis,
        generate_devotional_flow=generate_devotional_flow,
        generate_multimedia_digest=generate_multimedia_digest,
        build_sermon_deliverable=build_sermon_deliverable,
        build_sermon_prep_package=build_sermon_prep_package,
        build_transcript_deliverable=build_transcript_deliverable,
        build_transcript_package=build_transcript_package,
    )
)

# Delegate primary workflow helpers to the chat module ---------------------
GuardedAnswerPipeline = _chat_module.GuardedAnswerPipeline
_guarded_answer = _chat_module._guarded_answer
_guarded_answer_or_refusal = _chat_module._guarded_answer_or_refusal
run_guarded_chat = _chat_module.run_guarded_chat


__all__ = [
    "CollaborationResponse",
    "ComparativeAnalysisResponse",
    "CorpusCurationReport",
    "DevotionalResponse",
    "GuardedAnswerPipeline",
    "GuardrailError",
    "MultimediaDigestResponse",
    "RAGAnswer",
    "RAGCitation",
    "REFUSAL_MESSAGE",
    "REFUSAL_MODEL_NAME",
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
    "log_workflow_event",
    "record_used_citation_feedback",
    "run_corpus_curation",
    "run_guarded_chat",
    "run_research_reconciliation",
    "search_passages",
]


class _WorkflowModule(types.ModuleType):
    """Module proxy ensuring patches propagate to the chat implementation."""

    def __getattr__(self, name: str) -> Any:
        if hasattr(_chat_module, name):
            return getattr(_chat_module, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(_chat_module, name):
            setattr(_chat_module, name, value)
        if name == "log_workflow_event":
            _propagate_log_workflow_event(value)
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _WorkflowModule

