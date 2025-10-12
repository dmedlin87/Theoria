"""Security and throttling primitives for MCP tools."""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Deque, Dict, Iterable, Literal, MutableMapping, Tuple

from fastapi import status

from . import schemas

LOGGER = logging.getLogger(__name__)


class WriteSecurityError(RuntimeError):
    """Raised when a write request violates policy."""

    def __init__(self, message: str, *, status_code: int = status.HTTP_403_FORBIDDEN) -> None:
        super().__init__(message)
        self.status_code = status_code


def _parse_allowlist(value: str | None) -> Dict[str, set[str]]:
    if not value:
        return {}
    entries = {}
    for item in value.split(";"):
        if not item.strip():
            continue
        if "=" in item:
            tool, actors = item.split("=", 1)
        elif ":" in item:
            tool, actors = item.split(":", 1)
        else:
            continue
        actor_set = {actor.strip() for actor in actors.split(",") if actor.strip()}
        if not actor_set:
            continue
        entries[tool.strip()] = actor_set
    return entries


def _parse_rate_limits(value: str | None) -> Dict[str, int]:
    if not value:
        return {}
    limits: Dict[str, int] = {}
    for item in value.split(";"):
        if not item.strip():
            continue
        if "=" in item:
            tool, limit = item.split("=", 1)
        elif ":" in item:
            tool, limit = item.split(":", 1)
        else:
            continue
        tool_name = tool.strip()
        try:
            limits[tool_name] = int(limit.strip())
        except ValueError:
            continue
    return limits


@dataclass
class WriteSecurityPolicy:
    """Holds allowlist, rate limit, and idempotency caches for write tools."""

    allowlists: Dict[str, set[str]] = field(default_factory=dict)
    rate_limits: Dict[str, int] = field(default_factory=dict)
    window_seconds: int = 60
    _idempotency_cache: MutableMapping[Tuple[str, str, str], schemas.ToolResponseBase] = field(
        default_factory=dict
    )
    _rate_tracking: MutableMapping[Tuple[str, str], Deque[float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    _security_events: MutableMapping[str, int] = field(default_factory=dict)

    def _actors(self, tenant_id: str | None, end_user_id: str | None) -> Iterable[str]:
        if tenant_id:
            yield tenant_id
        if end_user_id:
            yield end_user_id

    def ensure_allowed(self, tool: str, commit: bool, tenant_id: str | None, end_user_id: str | None) -> None:
        if not commit:
            return
        allowed = self.allowlists.get(tool)
        if not allowed:
            return
        for actor in self._actors(tenant_id, end_user_id):
            if actor in allowed:
                return
        actor_id = next(iter(self._actors(tenant_id, end_user_id)), "unknown")
        self._log_security_event("access_denied", tool, actor=actor_id)
        raise WriteSecurityError(
            f"Writes to {tool} are not allowed for the supplied identity",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    def enforce_rate_limit(
        self, tool: str, commit: bool, tenant_id: str | None, end_user_id: str | None
    ) -> None:
        if not commit:
            return
        limit = self.rate_limits.get(tool)
        if not limit:
            return
        actor = next(iter(self._actors(tenant_id, end_user_id)), None)
        if actor is None:
            self._log_security_event("rate_limit_missing_actor", tool)
            raise WriteSecurityError(
                "Write requests must include an end_user_id or tenant scope",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        key = (tool, actor)
        now = time.time()
        with self._lock:
            bucket = self._rate_tracking.setdefault(key, deque())
            while bucket and now - bucket[0] > self.window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                self._log_security_event("rate_limit_exceeded", tool, actor=actor)
                raise WriteSecurityError(
                    "Rate limit exceeded for tool write",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            bucket.append(now)

    def resolve_cached_response(
        self,
        tool: str,
        commit: bool,
        tenant_id: str | None,
        end_user_id: str | None,
        idempotency_key: str | None,
    ) -> schemas.ToolResponseBase | None:
        if not commit or not idempotency_key:
            return None
        actor = next(iter(self._actors(tenant_id, end_user_id)), None)
        if actor is None:
            return None
        with self._lock:
            cached = self._idempotency_cache.get((tool, actor, idempotency_key))
            if cached is None:
                return None
            return cached.model_copy(deep=True)

    def store_idempotent_response(
        self,
        tool: str,
        tenant_id: str | None,
        end_user_id: str | None,
        idempotency_key: str | None,
        response: schemas.ToolResponseBase,
    ) -> None:
        if idempotency_key is None:
            return
        actor = next(iter(self._actors(tenant_id, end_user_id)), None)
        if actor is None:
            return
        with self._lock:
            self._idempotency_cache[(tool, actor, idempotency_key)] = response.model_copy(
                deep=True
            )

    def _log_security_event(
        self, event_type: str, tool: str, actor: str | None = None
    ) -> None:
        """Log security events for monitoring and auditing."""
        event_key = f"{event_type}:{tool}"
        with self._lock:
            self._security_events[event_key] = self._security_events.get(event_key, 0) + 1
        LOGGER.warning(
            "security.event",
            extra={
                "event_type": event_type,
                "tool": tool,
                "actor": actor,
                "timestamp": time.time(),
            },
        )

    def get_security_metrics(self) -> Dict[str, int]:
        """Return current security event counters for monitoring."""
        with self._lock:
            return dict(self._security_events)


@dataclass
class ReadSecurityPolicy:
    """Rate limiting and request validation for read operations."""

    rate_limits: Dict[str, int] = field(default_factory=dict)
    window_seconds: int = 60
    _rate_tracking: MutableMapping[Tuple[str, str], Deque[float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    _security_events: MutableMapping[str, int] = field(default_factory=dict)

    def enforce_rate_limit(self, tool: str, end_user_id: str) -> None:
        """Enforce rate limits on read operations."""
        limit = self.rate_limits.get(tool)
        if not limit:
            return
        if not end_user_id:
            self._log_security_event("rate_limit_missing_user", tool)
            raise WriteSecurityError(
                "Read requests must include an end_user_id for rate limiting",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        key = (tool, end_user_id)
        now = time.time()
        with self._lock:
            bucket = self._rate_tracking.setdefault(key, deque())
            while bucket and now - bucket[0] > self.window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                self._log_security_event("rate_limit_exceeded", tool, actor=end_user_id)
                raise WriteSecurityError(
                    f"Rate limit exceeded for {tool}",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            bucket.append(now)

    def _log_security_event(
        self, event_type: str, tool: str, actor: str | None = None
    ) -> None:
        """Log security events for monitoring and auditing."""
        event_key = f"{event_type}:{tool}"
        with self._lock:
            self._security_events[event_key] = self._security_events.get(event_key, 0) + 1
        LOGGER.warning(
            "security.event",
            extra={
                "event_type": event_type,
                "tool": tool,
                "actor": actor,
                "timestamp": time.time(),
            },
        )

    def get_security_metrics(self) -> Dict[str, int]:
        """Return current security event counters for monitoring."""
        with self._lock:
            return dict(self._security_events)


_WRITE_POLICY: WriteSecurityPolicy | None = None
_READ_POLICY: ReadSecurityPolicy | None = None


def get_write_security_policy() -> WriteSecurityPolicy:
    global _WRITE_POLICY
    if _WRITE_POLICY is None:
        allowlists = _parse_allowlist(os.getenv("MCP_WRITE_ALLOWLIST"))
        rate_limits = _parse_rate_limits(os.getenv("MCP_WRITE_RATE_LIMITS"))
        _WRITE_POLICY = WriteSecurityPolicy(allowlists=allowlists, rate_limits=rate_limits)
    return _WRITE_POLICY


def get_read_security_policy() -> ReadSecurityPolicy:
    global _READ_POLICY
    if _READ_POLICY is None:
        rate_limits = _parse_rate_limits(os.getenv("MCP_READ_RATE_LIMITS"))
        _READ_POLICY = ReadSecurityPolicy(rate_limits=rate_limits)
    return _READ_POLICY


def reset_write_security_policy() -> None:
    global _WRITE_POLICY
    _WRITE_POLICY = None


def reset_read_security_policy() -> None:
    global _READ_POLICY
    _READ_POLICY = None


__all__ = [
    "WriteSecurityPolicy",
    "ReadSecurityPolicy",
    "WriteSecurityError",
    "get_write_security_policy",
    "get_read_security_policy",
    "reset_write_security_policy",
    "reset_read_security_policy",
]
