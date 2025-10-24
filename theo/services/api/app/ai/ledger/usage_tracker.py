"""Utility helpers for capturing AI usage statistics."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from .. import AIProvider


@dataclass
class _UsageSnapshot:
    provider: AIProvider
    model: str
    start_time: datetime
    status: str = "active"


class UsageTracker:
    """Track active AI requests and aggregate usage statistics."""

    def __init__(self) -> None:
        self._active_requests: Dict[str, _UsageSnapshot] = {}
        self._usage_stats: Dict[AIProvider, Dict[str, float]] = {}

    async def start_request(self, provider: AIProvider, model: str) -> str:
        """Register the start of a request and return the request id."""

        request_id = f"{provider.value}:{model}:{datetime.utcnow().isoformat()}"
        self._active_requests[request_id] = _UsageSnapshot(
            provider=provider,
            model=model,
            start_time=datetime.utcnow(),
        )
        return request_id

    async def complete_request(
        self,
        provider: AIProvider,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration: float,
        request_id: Optional[str] = None,
    ) -> None:
        """Finalize a request and update aggregate statistics."""

        stats = self._usage_stats.setdefault(
            provider,
            {
                "total_requests": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_duration": 0.0,
                "average_duration": 0.0,
            },
        )

        stats["total_requests"] += 1
        stats["total_prompt_tokens"] += prompt_tokens
        stats["total_completion_tokens"] += completion_tokens
        stats["total_duration"] += duration
        stats["average_duration"] = (
            stats["total_duration"] / stats["total_requests"]
            if stats["total_requests"]
            else 0.0
        )

        if request_id is not None:
            self._active_requests.pop(request_id, None)

    def get_usage_stats(self, provider: Optional[AIProvider] = None) -> Dict[AIProvider, Dict[str, float]]:
        """Return aggregated usage metrics for providers."""

        if provider is not None:
            stats = self._usage_stats.get(provider)
            return {provider: stats or {}} if stats is not None else {}
        return dict(self._usage_stats)


__all__ = ["UsageTracker"]
