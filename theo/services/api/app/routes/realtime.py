"""Lightweight realtime collaboration hooks for notebooks."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, DefaultDict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..models.notebooks import NotebookRealtimeSnapshot
from ..security import Principal, require_principal, require_websocket_principal


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
            if connections and not connections:
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


@router.get(
    "/notebooks/{notebook_id}/poll",
    response_model=NotebookRealtimeSnapshot,
    dependencies=[Depends(require_principal)],
)
async def poll_notebook_events(notebook_id: str) -> NotebookRealtimeSnapshot:
    return _BROKER.snapshot(notebook_id)


__all__ = ["router", "publish_notebook_update"]
