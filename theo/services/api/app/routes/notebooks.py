"""CRUD routes for collaborative notebooks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session

from ..models.notebooks import (
    NotebookCreatePayload,
    NotebookEntryCreate,
    NotebookEntryResponse,
    NotebookEntryUpdate,
    NotebookListResponse,
    NotebookResponse,
    NotebookUpdatePayload,
)
from ..notebooks.service import NotebookService
from theo.application.security import Principal

from ..adapters.security import require_principal

router = APIRouter()


def _service(session: Session, principal: Principal | None) -> NotebookService:
    return NotebookService(session, principal)


@router.get("/", response_model=NotebookListResponse)
def list_notebooks(
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> NotebookListResponse:
    service = _service(session, principal)
    return service.list_notebooks()


@router.post("/", response_model=NotebookResponse, status_code=status.HTTP_201_CREATED)
def create_notebook(
    payload: NotebookCreatePayload,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> NotebookResponse:
    service = _service(session, principal)
    return service.create_notebook(payload)


@router.get("/{notebook_id}", response_model=NotebookResponse)
def get_notebook(
    notebook_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> NotebookResponse:
    service = _service(session, principal)
    return service.get_notebook(notebook_id)


@router.patch("/{notebook_id}", response_model=NotebookResponse)
def update_notebook(
    notebook_id: str,
    payload: NotebookUpdatePayload,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> NotebookResponse:
    service = _service(session, principal)
    return service.update_notebook(notebook_id, payload)


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook(
    notebook_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> Response:
    service = _service(session, principal)
    service.delete_notebook(notebook_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{notebook_id}/entries",
    response_model=NotebookEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notebook_entry(
    notebook_id: str,
    payload: NotebookEntryCreate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> NotebookEntryResponse:
    service = _service(session, principal)
    return service.create_entry(notebook_id, payload)


@router.patch("/entries/{entry_id}", response_model=NotebookEntryResponse)
def update_notebook_entry(
    entry_id: str,
    payload: NotebookEntryUpdate,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> NotebookEntryResponse:
    service = _service(session, principal)
    return service.update_entry(entry_id, payload)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook_entry(
    entry_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> Response:
    service = _service(session, principal)
    service.delete_entry(entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
