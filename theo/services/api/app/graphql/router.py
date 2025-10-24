"""FastAPI router exposing the GraphQL schema."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from strawberry.fastapi import GraphQLRouter

from ..security import require_principal
from .context import get_graphql_context
from .schema import schema

_graphql_app = GraphQLRouter(
    schema,
    path="/graphql",
    context_getter=get_graphql_context,
)

router = APIRouter()
router.include_router(
    _graphql_app,
    dependencies=[Depends(require_principal)],
)

__all__ = ["router", "_graphql_app"]
