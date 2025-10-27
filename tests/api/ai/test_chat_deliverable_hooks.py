"""Unit tests for the deliverable hook configuration on the chat module."""

from __future__ import annotations

import importlib


def test_configure_deliverable_hooks_updates_module_exports() -> None:
    """Registering hooks should swap the chat module's compatibility exports."""

    chat_module = importlib.reload(
        importlib.import_module("theo.infrastructure.api.app.ai.rag.chat")
    )

    def _outline_hook(*_args, **_kwargs):  # pragma: no cover - trivial lambda
        return "outline"

    def _comparative_hook(*_args, **_kwargs):  # pragma: no cover - trivial lambda
        return "comparative"

    def _devotional_hook(*_args, **_kwargs):  # pragma: no cover - trivial lambda
        return "devotional"

    def _multimedia_hook(*_args, **_kwargs):  # pragma: no cover - trivial lambda
        return "multimedia"

    def _build_sermon(*_args, **_kwargs):  # pragma: no cover - trivial lambda
        return "sermon"

    def _build_sermon_package(*_args, **_kwargs):  # pragma: no cover - trivial lambda
        return "sermon_package"

    def _build_transcript(*_args, **_kwargs):  # pragma: no cover - trivial lambda
        return "transcript"

    def _build_transcript_package(*_args, **_kwargs):  # pragma: no cover - trivial lambda
        return "transcript_package"

    hooks = chat_module.DeliverableHooks(
        generate_sermon_prep_outline=_outline_hook,
        generate_comparative_analysis=_comparative_hook,
        generate_devotional_flow=_devotional_hook,
        generate_multimedia_digest=_multimedia_hook,
        build_sermon_deliverable=_build_sermon,
        build_sermon_prep_package=_build_sermon_package,
        build_transcript_deliverable=_build_transcript,
        build_transcript_package=_build_transcript_package,
    )

    chat_module.configure_deliverable_hooks(hooks)

    assert chat_module.generate_sermon_prep_outline is _outline_hook
    assert chat_module.generate_comparative_analysis is _comparative_hook
    assert chat_module.generate_devotional_flow is _devotional_hook
    assert chat_module.generate_multimedia_digest is _multimedia_hook
    assert chat_module.build_sermon_deliverable is _build_sermon
    assert chat_module.build_sermon_prep_package is _build_sermon_package
    assert chat_module.build_transcript_deliverable is _build_transcript
    assert chat_module.build_transcript_package is _build_transcript_package

    # Reload the workflow shim to restore the production hooks for other tests.
    importlib.reload(importlib.import_module("theo.infrastructure.api.app.ai.rag.workflow"))
