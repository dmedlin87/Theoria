"""Export route package orchestrating specialised routers."""

from __future__ import annotations

from fastapi import APIRouter

from theo.application.facades import telemetry  # noqa: F401

from ...errors import ExportError
from ...export.formatters import build_search_export, render_bundle
from ...retriever.export import export_search_results
from ...export.zotero import export_to_zotero as _zotero_export_adapter
from . import citations, deliverables, documents, search, zotero

_normalise_formats = deliverables._normalise_formats

router = APIRouter()
router.include_router(citations.router)
router.include_router(deliverables.router)
router.include_router(search.router)
router.include_router(documents.router)
router.include_router(zotero.router)

api_router = APIRouter(prefix="/api")
api_router.include_router(router, prefix="/export")

export_to_zotero = _zotero_export_adapter

__all__ = [
    "router",
    "api_router",
    "ExportError",
    "export_to_zotero",
    "citations",
    "deliverables",
    "documents",
    "search",
    "zotero",
    "_normalise_formats",
    "export_search_results",
    "build_search_export",
    "render_bundle",
]
