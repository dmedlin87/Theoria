"""Lightweight realtime collaboration hooks for notebooks."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, DefaultDict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.datastructures import State

from ..models.notebooks import NotebookRealtimeSnapshot
from ..security import Principal, require_principal
from theo.application.facades.database import get_session

if TYPE_CHECKING:  # pragma: no cover - used only for type hints
    from ..notebooks.service import NotebookService


router = APIRouter()


class NotebookEventBroker:
    """In-memory notebook event dispatcher supporting websocket and polling."""

    def __init__(self) -> None:
        self._connections: DefaultDict[str, set[WebSocket]] = defaultdict(set)
        self._versions: DefaultDict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def connect(self, notebook_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[notebook_id].add(websocket)

    async def disconnect(self, notebook_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(notebook_id)
            if connections and websocket in connections:
                connections.remove(websocket)
            if connections is not None and not connections:
                self._connections.pop(notebook_id, None)

    def current_version(self, notebook_id: str) -> int:
        return self._versions[notebook_id]

    async def broadcast(self, notebook_id: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            self._versions[notebook_id] += 1
            version = self._versions[notebook_id]
            connections = list(self._connections.get(notebook_id, set()))
        message = {"type": "notebook.update", "version": version, **payload}
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                await self.disconnect(notebook_id, connection)

    def snapshot(self, notebook_id: str) -> NotebookRealtimeSnapshot:
        return NotebookRealtimeSnapshot(
            notebook_id=notebook_id,
            version=self._versions[notebook_id],
            updated_at=datetime.now(UTC),
        )


_BROKER = NotebookEventBroker()


def _service(session: Session, principal: Principal | None) -> "NotebookService":
    from ..notebooks.service import NotebookService

    return NotebookService(session, principal)


def require_websocket_principal(websocket: WebSocket) -> Principal:
    """Authenticate websocket connections using the standard principal helper."""

    state = websocket.scope.get("state")
    if not isinstance(state, State):
        state = State()
        websocket.scope["state"] = state
    request = SimpleNamespace(state=state)
    authorization = websocket.headers.get("authorization")
    api_key_header = websocket.headers.get("x-api-key")
    principal = require_principal(
        request,
        authorization=authorization,
        api_key_header=api_key_header,
    )
    websocket.state.principal = principal
    return principal


def publish_notebook_update(notebook_id: str, payload: dict[str, Any]) -> None:
    """Schedule a broadcast to connected notebook collaborators."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_BROKER.broadcast(notebook_id, payload))
        return
    loop.create_task(_BROKER.broadcast(notebook_id, payload))


@router.websocket("/notebooks/{notebook_id}")
async def notebook_updates(
    websocket: WebSocket,
    notebook_id: str,
    principal: Principal = Depends(require_websocket_principal),
) -> None:
    session_generator = get_session()
    session = next(session_generator)
    try:
        service = _service(session, principal)
        service.ensure_accessible(notebook_id)
    finally:
        session_generator.close()
    await _BROKER.connect(notebook_id, websocket)
    try:
        await websocket.send_json(
            {
                "type": "notebook.welcome",
                "notebook_id": notebook_id,
                "version": _BROKER.current_version(notebook_id),
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await _BROKER.disconnect(notebook_id, websocket)


@router.get("/notebooks/{notebook_id}/poll", response_model=NotebookRealtimeSnapshot)
async def poll_notebook_events(
    notebook_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> NotebookRealtimeSnapshot:
    service = _service(session, principal)
    service.ensure_accessible(notebook_id)
    return _BROKER.snapshot(notebook_id)


__all__ = ["router", "publish_notebook_update"]
