"""Theo Engine MCP server exposing tool metadata and stub handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from collections.abc import Mapping as ABCMapping, Sequence as ABCSequence
from typing import Any, Awaitable, Callable, Dict, Iterable, Literal, Mapping, Type, TypeVar, get_args, get_origin
from uuid import uuid4

from fastapi import FastAPI, Header
from . import schemas

LOGGER = logging.getLogger(__name__)


RequestModel = TypeVar("RequestModel", bound=schemas.ToolRequestBase)
ResponseModel = TypeVar("ResponseModel", bound=schemas.ToolResponseBase)


@dataclass(frozen=True)
class ToolDefinition:
    """Description of a single MCP tool."""

    name: str
    description: str
    request_model: Type[RequestModel]
    response_model: Type[ResponseModel]
    handler: Callable[[RequestModel, str], Awaitable[ResponseModel]]


def _placeholder_value(field: Any) -> Any:
    """Return a synthetic value for required response fields without defaults."""

    annotation = getattr(field, "annotation", Any)
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (list, tuple, set, frozenset, ABCSequence):
        return []
    if origin in (dict, ABCMapping):
        return {}
    if origin is Literal:
        return args[0] if args else None

    if annotation is str or annotation is Any:
        return ""
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0
    if annotation is bool:
        return False

    return ""


def _build_stub_handler(
    tool_name: str,
    response_model: Type[ResponseModel],
) -> Callable[[RequestModel, str], Awaitable[ResponseModel]]:
    """Return a stub handler that logs invocation metadata."""

    async def _handler(
        request: RequestModel,
        end_user_id: str = Header(..., alias="X-End-User-Id"),
    ) -> ResponseModel:
        run_id = str(uuid4())
        LOGGER.info(
            "Invoked MCP tool", extra={"tool": tool_name, "request_id": request.request_id, "run_id": run_id, "end_user_id": end_user_id}
        )
        response_kwargs: Dict[str, Any] = {
            "request_id": request.request_id,
            "dry_run": request.dry_run,
            "run_id": run_id,
        }

        for field_name, field in response_model.model_fields.items():
            if field_name in response_kwargs:
                continue
            if field.is_required():
                if hasattr(request, field_name):
                    response_kwargs[field_name] = getattr(request, field_name)
                else:
                    response_kwargs[field_name] = _placeholder_value(field)

        return response_model(**response_kwargs)

    return _handler


def _build_tools() -> tuple[ToolDefinition, ...]:
    """Define all MCP tools exposed by the server."""

    return (
        ToolDefinition(
            name="search_library",
            description="Search Theo's library for passages, documents, and cross references.",
            request_model=schemas.SearchLibraryRequest,
            response_model=schemas.SearchLibraryResponse,
            handler=_build_stub_handler("search_library", schemas.SearchLibraryResponse),
        ),
        ToolDefinition(
            name="aggregate_verses",
            description="Aggregate verse mentions across the Theo corpus.",
            request_model=schemas.AggregateVersesRequest,
            response_model=schemas.AggregateVersesResponse,
            handler=_build_stub_handler("aggregate_verses", schemas.AggregateVersesResponse),
        ),
        ToolDefinition(
            name="get_timeline",
            description="Return aggregated timeline information for a verse.",
            request_model=schemas.GetTimelineRequest,
            response_model=schemas.GetTimelineResponse,
            handler=_build_stub_handler("get_timeline", schemas.GetTimelineResponse),
        ),
        ToolDefinition(
            name="quote_lookup",
            description="Retrieve transcript quotes linked to passages or identifiers.",
            request_model=schemas.QuoteLookupRequest,
            response_model=schemas.QuoteLookupResponse,
            handler=_build_stub_handler("quote_lookup", schemas.QuoteLookupResponse),
        ),
        ToolDefinition(
            name="note_write",
            description="Create or update a research note anchored to an OSIS reference.",
            request_model=schemas.NoteWriteRequest,
            response_model=schemas.NoteWriteResponse,
            handler=_build_stub_handler("note_write", schemas.NoteWriteResponse),
        ),
        ToolDefinition(
            name="index_refresh",
            description="Request a refresh of Theo's background indexes.",
            request_model=schemas.IndexRefreshRequest,
            response_model=schemas.IndexRefreshResponse,
            handler=_build_stub_handler("index_refresh", schemas.IndexRefreshResponse),
        ),
        ToolDefinition(
            name="source_registry_list",
            description="List the registered MCP content sources.",
            request_model=schemas.SourceRegistryListRequest,
            response_model=schemas.SourceRegistryListResponse,
            handler=_build_stub_handler("source_registry_list", schemas.SourceRegistryListResponse),
        ),
        ToolDefinition(
            name="evidence_card_create",
            description="Create an evidence card that can be attached to research workflows.",
            request_model=schemas.EvidenceCardCreateRequest,
            response_model=schemas.EvidenceCardCreateResponse,
            handler=_build_stub_handler("evidence_card_create", schemas.EvidenceCardCreateResponse),
        ),
    )


TOOLS: tuple[ToolDefinition, ...] = _build_tools()

app = FastAPI(title="Theo Engine MCP Server", version="0.1.0")


def _register_tool_routes(application: FastAPI, tools: Iterable[ToolDefinition]) -> None:
    """Register POST routes for each tool definition."""

    for tool in tools:
        application.post(
            f"/tools/{tool.name}",
            response_model=tool.response_model,
            name=f"tool_{tool.name}",
        )(tool.handler)


_register_tool_routes(app, TOOLS)


def _collect_schemas(tools: Iterable[ToolDefinition]) -> Mapping[str, Dict[str, Any]]:
    """Build JSON Schema documents for every tool."""

    schema_map: dict[str, Dict[str, Any]] = {}
    for tool in tools:
        request_schema_id = f"https://theoengine.dev/mcp/schemas/{tool.name}.request.json"
        response_schema_id = f"https://theoengine.dev/mcp/schemas/{tool.name}.response.json"

        request_schema = tool.request_model.model_json_schema()
        response_schema = tool.response_model.model_json_schema()

        request_schema["$id"] = request_schema_id
        response_schema["$id"] = response_schema_id

        schema_map[request_schema_id] = request_schema
        schema_map[response_schema_id] = response_schema

    return schema_map


@app.get("/metadata", response_model=dict[str, Any])
def metadata() -> Dict[str, Any]:
    """Return MCP metadata including tool descriptions and JSON Schemas."""

    tools_payload: list[Dict[str, Any]] = []
    schemas_payload = _collect_schemas(TOOLS)

    for tool in TOOLS:
        request_schema_id = f"https://theoengine.dev/mcp/schemas/{tool.name}.request.json"
        response_schema_id = f"https://theoengine.dev/mcp/schemas/{tool.name}.response.json"
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


@app.post("/health", response_model=dict[str, str])
def healthcheck() -> Dict[str, str]:
    """Simple healthcheck endpoint for deployments."""

    return {"status": "ok"}
