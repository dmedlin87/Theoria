"""Lightweight event bus utilities used across Theo services."""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from threading import RLock
from typing import Any, Callable, Hashable

EventHandler = Callable[[Any], Any]
EventKey = Hashable

logger = logging.getLogger("theo.platform.events")


class EventBus:
    """Simple publish/subscribe event bus.

    Handlers are invoked synchronously by default in the order they were
    registered.  Call :meth:`publish_async` or pass ``async_dispatch=True`` to
    :meth:`publish` when running inside an asyncio event loop.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventKey, list[EventHandler]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, key: EventKey, handler: EventHandler) -> None:
        """Register *handler* for events matching *key*."""

        if key is None:
            raise ValueError("event key must not be None")
        if not callable(handler):
            raise TypeError("event handler must be callable")
        with self._lock:
            handlers = self._handlers[key]
            if handler in handlers:
                return
            handlers.append(handler)

    def unsubscribe(self, key: EventKey, handler: EventHandler) -> None:
        """Remove *handler* from the subscription list for *key*."""

        with self._lock:
            handlers = self._handlers.get(key)
            if not handlers:
                return
            try:
                handlers.remove(handler)
            except ValueError:
                return
            if not handlers:
                self._handlers.pop(key, None)

    def publish(
        self,
        event: Any | None = None,
        *,
        key: EventKey | None = None,
        async_dispatch: bool = False,
    ) -> list[Any] | asyncio.Future[list[Any]] | asyncio.Task[list[Any]]:
        """Dispatch *event* to subscribed handlers.

        When *async_dispatch* is ``True`` the coroutine returned from
        :meth:`publish_async` is scheduled and returned.  Callers are expected to
        await or manage the returned task.
        """

        if async_dispatch:
            coro = self.publish_async(event, key=key)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.ensure_future(coro)
            return loop.create_task(coro)
        return self._dispatch_sync(event, key)

    async def publish_async(
        self, event: Any | None = None, *, key: EventKey | None = None
    ) -> list[Any]:
        """Asynchronously dispatch *event* to subscribed handlers."""

        handlers = self._snapshot_handlers(key or self._derive_key(event))
        results: list[Any] = []
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    result = await result  # type: ignore[assignment]
            except Exception:  # pragma: no cover - handler failure safety
                logger.exception("event handler failed", extra={"handler": handler})
                continue
            results.append(result)
        return results

    def clear(self) -> None:
        """Remove all registered handlers (primarily for testing)."""

        with self._lock:
            self._handlers.clear()

    def _dispatch_sync(self, event: Any | None, key: EventKey | None) -> list[Any]:
        handlers = self._snapshot_handlers(key or self._derive_key(event))
        results: list[Any] = []
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    result = asyncio.run(result)  # type: ignore[arg-type]
            except RuntimeError as exc:
                message = str(exc)
                if "asyncio.run" in message:
                    logger.exception(
                        "async handler requires publish_async",
                        extra={"handler": handler},
                    )
                else:  # pragma: no cover - unexpected runtime errors
                    logger.exception(
                        "event handler failed", extra={"handler": handler}
                    )
                continue
            except Exception:  # pragma: no cover - handler failure safety
                logger.exception("event handler failed", extra={"handler": handler})
                continue
            results.append(result)
        return results

    def _derive_key(self, event: Any | None) -> EventKey:
        if event is None:
            raise ValueError("event instance or explicit key required")
        return event.__class__

    def _snapshot_handlers(self, key: EventKey) -> list[EventHandler]:
        with self._lock:
            handlers = list(self._handlers.get(key, ()))
        return handlers


event_bus = EventBus()

__all__ = ["EventBus", "EventHandler", "event_bus"]
