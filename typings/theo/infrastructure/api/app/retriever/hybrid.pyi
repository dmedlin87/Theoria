from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from theo.infrastructure.api.app.models.search import (
    HybridSearchRequest,
    HybridSearchResult,
)


def hybrid_search(
    session: Session,
    request: HybridSearchRequest,
) -> Sequence[HybridSearchResult]: ...


__all__ = ["hybrid_search"]
