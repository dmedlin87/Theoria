"""Theo Engine MCP server exposing tool metadata and handlers."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Any, Awaitable, Callable, Dict, Generic, Iterable, Mapping, TypeVar, cast
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from . import schemas
from .config import ServerConfig
from .errors import MCPError, mcp_error_handler, generic_error_handler
from .metrics import get_metrics_collector
from .middleware import (
    CORSHeaderMiddleware,
    RequestIDMiddleware,
    RequestLimitMiddleware,
    RequestTimingMiddleware,
    SecurityHeadersMiddleware,
)
from .tools import read, write

LOGGER = logging.getLogger(__name__)


RequestModelT = TypeVar("RequestModelT", bound=schemas.ToolRequestBase)
ResponseModelT = TypeVar("ResponseModelT", bound=schemas.ToolResponseBase)


@dataclass(frozen=True)
class ToolDefinition(Generic[RequestModelT, ResponseModelT]):
    """Description of a single MCP tool."""

    name: str
    description: str
    request_model: type[RequestModelT]
    response_model: type[ResponseModelT]
    handler: Callable[..., Awaitable[ResponseModelT]]


def _build_stub_handler(
    tool_name: str,
    response_model: type[ResponseModelT],
) -> Callable[..., Awaitable[ResponseModelT]]:
    """Return a stub handler that logs invocation metadata."""

    async def _handler(
        request: RequestModelT,
        end_user_id: Annotated[str, Header(alias="X-End-User-Id")],
    ) -> ResponseModelT:
        run_id = str(uuid4())
        LOGGER.info(
            "Invoked MCP tool",
            extra={
                "tool": tool_name,
                "request_id": request.request_id,
                "run_id": run_id,
                "end_user_id": end_user_id,
            },
        )
        return response_model(
            request_id=request.request_id,
            commit=request.commit,
            run_id=run_id,
        )

    return cast(Callable[..., Awaitable[ResponseModelT]], _handler)


def _schema_base_url() -> str:
    """Return the base URL used when emitting JSON Schema identifiers."""

    base = os.getenv("MCP_SCHEMA_BASE_URL", "https://theoengine.dev/mcp/schemas")
    return base.rstrip("/")


def _schema_ref(tool_name: str, direction: str) -> str:
    """Build a stable schema URL for the given tool and direction."""

    base = _schema_base_url()
    return f"{base}/{tool_name}.{direction}.json"


def _build_tools() -> tuple[ToolDefinition, ...]:
    """Define all MCP tools exposed by the server."""

    return (
        ToolDefinition(
            name="search_library",
            description="Search Theo's library for passages, documents, and cross references.",
            request_model=schemas.SearchLibraryRequest,
            response_model=schemas.SearchLibraryResponse,
            handler=read.search_library,
        ),
        ToolDefinition(
            name="aggregate_verses",
            description="Aggregate verse mentions across the Theo corpus.",
            request_model=schemas.AggregateVersesRequest,
            response_model=schemas.AggregateVersesResponse,
            handler=read.aggregate_verses,
        ),
        ToolDefinition(
            name="get_timeline",
            description="Return aggregated timeline information for a verse.",
            request_model=schemas.GetTimelineRequest,
            response_model=schemas.GetTimelineResponse,
            handler=read.get_timeline,
        ),
        ToolDefinition(
            name="quote_lookup",
            description="Retrieve transcript quotes linked to passages or identifiers.",
            request_model=schemas.QuoteLookupRequest,
            response_model=schemas.QuoteLookupResponse,
            handler=read.quote_lookup,
        ),
        ToolDefinition(
            name="note_write",
            description="Create or update a research note anchored to an OSIS reference.",
            request_model=schemas.NoteWriteRequest,
            response_model=schemas.NoteWriteResponse,
            handler=write.note_write,
        ),
        ToolDefinition(
            name="index_refresh",
            description="Request a refresh of Theo's background indexes.",
            request_model=schemas.IndexRefreshRequest,
            response_model=schemas.IndexRefreshResponse,
            handler=write.index_refresh,
        ),
        ToolDefinition(
            name="source_registry_list",
            description="List the registered MCP content sources.",
            request_model=schemas.SourceRegistryListRequest,
            response_model=schemas.SourceRegistryListResponse,
            handler=read.source_registry_list,
        ),
        ToolDefinition(
            name="evidence_card_create",
            description="Create an evidence card that can be attached to research workflows.",
            request_model=schemas.EvidenceCardCreateRequest,
            response_model=schemas.EvidenceCardCreateResponse,
            handler=write.evidence_card_create,
        ),
    )


def _tools_enabled() -> bool:
    """Return True when MCP tool endpoints should be exposed."""

    raw = os.getenv("MCP_TOOLS_ENABLED")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Load configuration
CONFIG = ServerConfig.from_env()

TOOLS: tuple[ToolDefinition[Any, Any], ...] = (
    _build_tools() if CONFIG.tools_enabled else tuple()
)

# Initialize FastAPI application
app = FastAPI(
    title=CONFIG.name,
    version=CONFIG.version,
    description="Model Context Protocol server for Theo theological research engine",
    docs_url="/docs" if CONFIG.debug else None,
    redoc_url="/redoc" if CONFIG.debug else None,
)

# Register error handlers
app.add_exception_handler(MCPError, mcp_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Register middleware (order matters - later middleware wraps earlier)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    RequestLimitMiddleware,
    max_body_size=CONFIG.max_request_body_size,
)

# Add CORS if origins configured
if CONFIG.cors_allow_origins:
    app.add_middleware(
        CORSHeaderMiddleware,
        allow_origins=CONFIG.cors_allow_origins,
        allow_credentials=CONFIG.cors_allow_credentials,
    )


def _register_tool_routes(application: FastAPI, tools: Iterable[ToolDefinition]) -> None:
    """Register POST routes for each tool definition."""

    for tool in tools:
        application.add_api_route(
            f"/tools/{tool.name}",
            tool.handler,
            response_model=tool.response_model,
            name=f"tool_{tool.name}",
            methods=["POST"],
        )


_register_tool_routes(app, TOOLS)


def _collect_schemas(tools: Iterable[ToolDefinition[Any, Any]]) -> Mapping[str, Dict[str, Any]]:
    """Build JSON Schema documents for every tool."""

    schema_map: dict[str, Dict[str, Any]] = {}
    for tool in tools:
        request_schema_id = _schema_ref(tool.name, "request")
        response_schema_id = _schema_ref(tool.name, "response")

        request_schema = tool.request_model.model_json_schema()
        response_schema = tool.response_model.model_json_schema()

        request_schema["$id"] = request_schema_id
        response_schema["$id"] = response_schema_id

        schema_map[request_schema_id] = request_schema
        schema_map[response_schema_id] = response_schema

    return schema_map


def metadata() -> Dict[str, Any]:
    """Return MCP metadata including tool descriptions and JSON Schemas."""

    tools_payload: list[Dict[str, Any]] = []
    schemas_payload = _collect_schemas(TOOLS)

    for tool in TOOLS:
        request_schema_id = _schema_ref(tool.name, "request")
        response_schema_id = _schema_ref(tool.name, "response")
        tools_payload.append(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {"$ref": request_schema_id},
                "output_schema": {"$ref": response_schema_id},
            }
        )

    return {
        "name": "theo-mcp-server",
        "version": "0.1.0",
        "tools": tools_payload,
        "schemas": schemas_payload,
    }


def healthcheck() -> Dict[str, Any]:
    """Enhanced healthcheck endpoint with service status."""
    from .security import get_read_security_policy, get_write_security_policy

    status_info: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": CONFIG.version,
        "environment": CONFIG.environment,
    }

    # Include service checks in debug mode
    if CONFIG.debug:
        status_info["services"] = {
            "tools_enabled": CONFIG.tools_enabled,
            "tools_count": len(TOOLS),
            "metrics_enabled": CONFIG.metrics_enabled,
        }

        # Security policy status
        read_policy = get_read_security_policy()
        write_policy = get_write_security_policy()
        status_info["security"] = {
            "read_rate_limits": len(read_policy.rate_limits),
            "write_rate_limits": len(write_policy.rate_limits),
            "write_allowlists": len(write_policy.allowlists),
        }

    return status_info


def metrics() -> Dict[str, Any]:
    """Expose operational metrics for monitoring."""
    if not CONFIG.metrics_enabled:
        return {"error": "Metrics collection is disabled"}

    collector = get_metrics_collector()
    metrics_data = collector.get_metrics_summary()

    # Include security metrics
    from .security import get_read_security_policy, get_write_security_policy

    read_policy = get_read_security_policy()
    write_policy = get_write_security_policy()

    metrics_data["security"] = {
        "read_events": read_policy.get_security_metrics(),
        "write_events": write_policy.get_security_metrics(),
    }

    return metrics_data


app.get("/metadata", response_model=dict[str, Any])(metadata)
app.get("/health", response_model=dict[str, Any])(healthcheck)
app.get("/metrics", response_model=dict[str, Any])(metrics)
