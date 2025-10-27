"""Context objects passed to GraphQL resolvers."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session
from strawberry.fastapi.context import BaseContext

from theo.application.facades.database import get_session
from theo.application.research import ResearchService
from theo.application.services import ApplicationContainer
from theo.application.security import Principal
from theo.application.services.bootstrap import resolve_application


class GraphQLContext(BaseContext):
    """Request-scoped objects made available to GraphQL resolvers."""

    def __init__(
        self,
        *,
        request: Request,
        session: Session,
        principal: Principal | None,
        application: ApplicationContainer,
        research_service: ResearchService,
    ) -> None:
        super().__init__()
        self.request = request
        self.session = session
        self.principal = principal
        self.application = application
        self.research_service = research_service


async def get_graphql_context(
    request: Request,
    session: Session = Depends(get_session),
) -> GraphQLContext:
    """Build the GraphQL execution context for the current request."""

    container, _registry = resolve_application()
    principal = getattr(request.state, "principal", None)
    research_service = container.get_research_service(session)
    return GraphQLContext(
        request=request,
        session=session,
        principal=principal,
        application=container,
        research_service=research_service,
    )
