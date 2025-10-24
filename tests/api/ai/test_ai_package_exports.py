"""Regression tests for the modular AI package surface."""

from __future__ import annotations

import importlib
import types

import pytest


def reload_ai_module():
    """Reload the ai package to ensure tests see latest exports."""

    ai_module = importlib.import_module("theo.services.api.app.ai")
    return importlib.reload(ai_module)


@pytest.mark.parametrize(
    "attribute_name",
    [
        "run_guarded_chat",
        "generate_sermon_prep_outline",
        "generate_multimedia_digest",
        "build_transcript_deliverable",
        "generate_verse_brief",
        "run_corpus_curation",
        "run_research_reconciliation",
    ],
)
def test_ai_package_reexports_rag_workflow_helpers(attribute_name: str) -> None:
    """The ai package should re-export guardrailed workflow helpers."""

    ai_module = reload_ai_module()
    rag_module = ai_module.rag

    exported = getattr(ai_module, attribute_name, None)
    rag_exported = getattr(rag_module, attribute_name, None)

    assert callable(exported), f"Expected {attribute_name} to be callable"
    assert exported is rag_exported, (
        "Guardrailed workflow helper should resolve to the rag module export"
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "digest_service",
        "memory_index",
        "passage",
        "research_loop",
        "router",
        "trails",
        "trails_memory_bridge",
    ],
)
def test_ai_package_exposes_legacy_submodules(module_name: str) -> None:
    """Legacy submodules remain reachable while migrations complete."""

    ai_module = reload_ai_module()

    exported = getattr(ai_module, module_name, None)
    assert isinstance(exported, types.ModuleType), (
        "Expected %s to remain importable as a module from ai package" % module_name
    )
    assert exported.__name__.startswith("theo.services.api.app.ai."), (
        "Module %s should report fully qualified name under ai package" % module_name
    )
