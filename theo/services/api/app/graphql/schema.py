"""GraphQL schema definitions for Theo's API."""

from __future__ import annotations

from typing import Any

import strawberry
from strawberry.types import Info

from theo.domain import DocumentId

from .context import GraphQLContext
from .types import (
    DocumentInput,
    DocumentType,
    InsightType,
    IngestDocumentPayload,
    VerseType,
)


@strawberry.type
class Query:
    """Root GraphQL query type."""

    @strawberry.field
    def documents(
        self,
        info: Info[GraphQLContext, Any],
        limit: int = 20,
    ) -> list[DocumentType]:
        """Return a list of indexed documents."""

        documents = info.context.application.list_documents(limit=limit)
        return [DocumentType.from_domain(document) for document in documents]

    @strawberry.field
    def document(
        self,
        info: Info[GraphQLContext, Any],
        id: strawberry.ID,
    ) -> DocumentType | None:
        """Fetch a single document by identifier."""

        document = info.context.application.get_document(DocumentId(str(id)))
        if document is None:
            return None
        return DocumentType.from_domain(document)

    @strawberry.field
    def passage(
        self,
        info: Info[GraphQLContext, Any],
        osis: str,
        translation: str | None = None,
    ) -> list[VerseType]:
        """Return verses for the requested OSIS reference."""

        verses = info.context.research_service.fetch_passage(osis, translation=translation)
        return [VerseType.from_domain(verse) for verse in verses]

    @strawberry.field
    def insights(
        self,
        info: Info[GraphQLContext, Any],
        osis: str,
        mode: str | None = None,
    ) -> list[InsightType]:
        """Return a flattened list of reliability overview insights."""

        overview = info.context.research_service.build_reliability_overview(
            osis=osis,
            mode=mode,
        )
        insights: list[InsightType] = []
        for bullet in overview.consensus:
            insights.append(InsightType.from_overview("consensus", bullet))
        for bullet in overview.disputed:
            insights.append(InsightType.from_overview("disputed", bullet))
        for bullet in overview.manuscripts:
            insights.append(InsightType.from_overview("manuscript", bullet))
        return insights


@strawberry.type
class Mutation:
    """Root GraphQL mutation type."""

    @strawberry.mutation
    def ingest_document(
        self,
        info: Info[GraphQLContext, Any],
        input: DocumentInput,
    ) -> IngestDocumentPayload:
        """Ingest a new document into the system."""

        document = input.to_domain()
        document_id = info.context.application.ingest_document(document)
        return IngestDocumentPayload.from_document_id(document_id)


schema = strawberry.Schema(query=Query, mutation=Mutation)

__all__ = ["schema", "Query", "Mutation"]
