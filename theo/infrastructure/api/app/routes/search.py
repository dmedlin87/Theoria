"""Search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session

from ..ingest.embeddings import clear_embedding_cache
from ..models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResponse,
)
from ..infra.retrieval_service import (
    RetrievalService,
    get_retrieval_service,
    reset_reranker_cache as _reset_reranker_cache,
)

_MAX_EXPERIMENT_HEADER_LENGTH = 512
_MAX_EXPERIMENT_TOKEN_COUNT = 20
_MAX_EXPERIMENT_TOKEN_LENGTH = 64

router = APIRouter()


def reset_reranker_cache() -> None:
    """Expose a reset hook for tests.

    Clears both reranker and embedding caches to minimise cross-test state.
    """

    _reset_reranker_cache()
    clear_embedding_cache()


def _parse_experiment_tokens(tokens: list[str]) -> dict[str, str]:
    experiments: dict[str, str] = {}
    for token in tokens:
        if not token:
            continue
        if "=" in token:
            key, value = token.split("=", 1)
        elif ":" in token:
            key, value = token.split(":", 1)
        else:
            key, value = token, "1"
        experiments[key.strip().casefold()] = value.strip()
    return experiments


def _validate_experiment_tokens(tokens: list[str]) -> list[str]:
    """Validate experiment tokens and return the cleaned list."""

    cleaned = [token for token in tokens if token]
    if len(cleaned) > _MAX_EXPERIMENT_TOKEN_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Too many experiment flags supplied; "
                f"limit is {_MAX_EXPERIMENT_TOKEN_COUNT}."
            ),
        )
    for token in cleaned:
        if len(token) > _MAX_EXPERIMENT_TOKEN_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Experiment flag entries must be shorter than "
                    f"{_MAX_EXPERIMENT_TOKEN_LENGTH} characters."
                ),
            )
    return cleaned


@router.get("/", response_model=HybridSearchResponse)
def search(
    response: Response,
    request: Request,
    q: str | None = Query(default=None, description="Keyword query"),
    osis: str | None = Query(default=None, description="Normalized OSIS reference"),
    collection: str | None = Query(
        default=None, description="Restrict to a collection"
    ),
    author: str | None = Query(default=None, description="Filter by author"),
    source_type: str | None = Query(
        default=None, description="Restrict to a source type"
    ),
    perspective: str | None = Query(
        default=None,
        description="Bias retrieval toward an interpretive perspective",
    ),
    theological_tradition: str | None = Query(
        default=None,
        description="Restrict to documents aligned with a theological tradition",
    ),
    topic_domain: str | None = Query(
        default=None,
        description="Restrict to documents tagged with a topic domain",
    ),
    k: int = Query(default=10, ge=1, le=50),
    experiment: list[str] | None = Query(
        default=None,
        alias="experiment",
        description="Search experiment flags in key=value form",
    ),
    session: Session = Depends(get_session),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> HybridSearchResponse:
    """Perform hybrid search over the indexed corpus."""

    normalized_perspective = (perspective or "").strip().casefold()
    perspective_tradition = None
    if normalized_perspective in {"skeptical", "apologetic", "neutral"}:
        perspective_tradition = normalized_perspective

    request_payload = HybridSearchRequest(
        query=q,
        osis=osis,
        filters=HybridSearchFilters(
            collection=collection,
            author=author,
            source_type=source_type,
            theological_tradition=theological_tradition or perspective_tradition,
            topic_domain=topic_domain,
        ),
        k=k,
    )
    experiment_tokens: list[str] = []
    header_tokens = request.headers.get("X-Search-Experiments")
    if header_tokens:
        if len(header_tokens) > _MAX_EXPERIMENT_HEADER_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "X-Search-Experiments header exceeds the maximum allowed length."
                ),
            )
        experiment_tokens.extend([token.strip() for token in header_tokens.split(",")])
    if experiment:
        experiment_tokens.extend(experiment)
    experiment_tokens = _validate_experiment_tokens(experiment_tokens)
    experiments = _parse_experiment_tokens(experiment_tokens)

    results, reranker_header = retrieval_service.search(
        session,
        request_payload,
        experiments=experiments,
    )

    if reranker_header:
        response.headers["X-Reranker"] = reranker_header

    return HybridSearchResponse(query=q, osis=osis, results=results)
