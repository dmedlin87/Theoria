"""FastAPI router exposing the GraphQL schema."""

from __future__ import annotations

from strawberry.fastapi import GraphQLRouter

from .context import get_graphql_context
from .schema import schema

graphql_router = GraphQLRouter(
    schema,
    context_getter=get_graphql_context,
)

__all__ = ["graphql_router"]
