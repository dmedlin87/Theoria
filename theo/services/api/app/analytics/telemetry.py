"""Helpers for ingesting client-side telemetry."""

from __future__ import annotations

import logging

from ..models.analytics import TelemetryBatch

LOGGER = logging.getLogger(__name__)


def record_client_telemetry(batch: TelemetryBatch) -> None:
    """Log client telemetry events for downstream processing."""

    for event in batch.events:
        LOGGER.info(
            "client.telemetry",
            extra={
                "page": batch.page,
                "event": event.event,
                "duration_ms": event.duration_ms,
                "workflow": event.workflow,
                "metadata": event.metadata or {},
            },
        )
