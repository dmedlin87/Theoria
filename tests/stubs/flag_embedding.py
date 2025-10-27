"""Stub implementations of the FlagEmbedding package."""

from __future__ import annotations

from types import ModuleType
from typing import Iterable, List

__all__ = ["build_flag_embedding_stub"]


class _StubFlagModel:
    def __init__(self, *_, **__):
        self._dimension = 1024

    def encode(self, texts: Iterable[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for index, _ in enumerate(texts):
            base = float((index % 100) + 1)
            vectors.append([
                ((base + offset) % 100) / 100.0 for offset in range(self._dimension)
            ])
        return vectors


def build_flag_embedding_stub() -> dict[str, ModuleType]:
    module = ModuleType("FlagEmbedding")
    module.FlagModel = _StubFlagModel  # type: ignore[attr-defined]
    return {"FlagEmbedding": module}
