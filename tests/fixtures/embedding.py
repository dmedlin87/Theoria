"""Shared helpers for patching the embedding service module in tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable, Optional
import sys
import types

import pytest

from theo.application.facades.resilience import ResilienceError


@dataclass
class EmbeddingServicePatch:
    """Track calls against a stubbed embedding service module."""

    module: ModuleType
    clear_cache_calls: list[tuple[tuple[object, ...], dict[str, object]]] = field(
        default_factory=list
    )
    factory_calls: list[tuple[tuple[object, ...], dict[str, object]]] = field(
        default_factory=list
    )
    _service_factory: Optional[Callable[[], object]] = None

    def set_service_factory(self, factory: Callable[[], object]) -> None:
        """Provide a factory used when the CLI resolves the embedding service."""

        self._service_factory = factory

    def set_service(self, service: object) -> None:
        """Return a constant service instance when requested by the CLI."""

        self._service_factory = lambda: service

    def resolve_service(self) -> object:
        """Return the configured service instance.

        Raises:
            RuntimeError: if no service factory has been configured.
        """

        if self._service_factory is None:
            raise RuntimeError("embedding service patch has no configured factory")
        return self._service_factory()

    def reset(self) -> None:
        """Clear tracked call metadata between tests."""

        self.clear_cache_calls.clear()
        self.factory_calls.clear()


_MODULE_NAME = "theo.infrastructure.api.app.ingest.embeddings"


def _create_stub_module(patch: EmbeddingServicePatch) -> ModuleType:
    module = types.ModuleType(_MODULE_NAME)

    def _clear_embedding_cache(*args: object, **kwargs: object) -> None:
        patch.clear_cache_calls.append((args, kwargs))

    def _get_embedding_service(*args: object, **kwargs: object) -> object:
        patch.factory_calls.append((args, kwargs))
        return patch.resolve_service()

    module.clear_embedding_cache = _clear_embedding_cache  # type: ignore[attr-defined]
    module.get_embedding_service = _get_embedding_service  # type: ignore[attr-defined]
    module.lexical_representation = lambda *_a, **_k: "lexical"  # type: ignore[attr-defined]
    module.EmbeddingService = object  # type: ignore[attr-defined]
    module.ResilienceError = ResilienceError  # type: ignore[attr-defined]
    return module


def install_embedding_service_patch() -> EmbeddingServicePatch:
    """Install the embedding service stub in ``sys.modules`` immediately."""

    patch = EmbeddingServicePatch(module=ModuleType("placeholder"))
    stub = _create_stub_module(patch)
    patch.module = stub
    sys.modules[_MODULE_NAME] = stub
    return patch


@pytest.fixture()
def embedding_service_patch(monkeypatch: pytest.MonkeyPatch) -> EmbeddingServicePatch:
    """Patch the embedding service module with lightweight test doubles."""

    patch = EmbeddingServicePatch(module=ModuleType("placeholder"))
    stub = _create_stub_module(patch)
    patch.module = stub

    monkeypatch.setitem(sys.modules, _MODULE_NAME, stub)

    yield patch

    patch.reset()
