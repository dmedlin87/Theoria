"""Ranking utilities for hybrid search results."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .features import FEATURE_NAMES, extract_features
from .metrics import dcg, mrr, ndcg

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from .re_ranker import Reranker, load_reranker

__all__ = [
    "FEATURE_NAMES",
    "extract_features",
    "dcg",
    "mrr",
    "ndcg",
    "Reranker",
    "load_reranker",
]


def __getattr__(name: str) -> Any:
    """Lazily expose heavy reranker helpers on demand."""

    if name in {"Reranker", "load_reranker"}:
        module = import_module(".re_ranker", __name__)
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
