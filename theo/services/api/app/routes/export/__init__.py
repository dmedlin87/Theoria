"""Export route package orchestrating specialised routers."""

from __future__ import annotations

from fastapi import APIRouter

from ...errors import ExportError
from ...export.zotero import export_to_zotero
from . import citations, deliverables, documents, search, zotero

router = APIRouter()
router.include_router(citations.router)
router.include_router(deliverables.router)
router.include_router(search.router)
router.include_router(documents.router)
router.include_router(zotero.router)

api_router = APIRouter(prefix="/api")
api_router.include_router(router, prefix="/export")

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
]
