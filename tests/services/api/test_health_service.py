from __future__ import annotations

import pytest

from theo.services.api.app.infra.health import (
    AdapterHealth,
    HealthProbeError,
    HealthService,
    HealthStatus,
)


def test_health_service_collates_probe_results() -> None:
    calls: list[str] = []

    def healthy_probe() -> str:
        calls.append("healthy")
        return "ok"

    def degraded_probe() -> str:
        calls.append("degraded")
        raise HealthProbeError("Redis cache cold", status=HealthStatus.DEGRADED)

    service = HealthService({"db": healthy_probe, "redis": degraded_probe})

    report = service.check()

    assert report.status is HealthStatus.DEGRADED
    assert set(report.adapters.keys()) == {"db", "redis"}
    assert report.adapters["db"].status is HealthStatus.HEALTHY
    assert report.adapters["redis"].status is HealthStatus.DEGRADED

    summary = report.to_summary()
    detail = report.to_detail()

    assert summary["status"] == "degraded"
    assert "redis" in summary["message"].lower()
    assert detail["adapters"][1]["name"] == "redis"
    assert detail["adapters"][1]["status"] == "degraded"
    assert calls == ["healthy", "degraded"]


def test_health_service_marks_unhandled_exceptions_unavailable() -> None:
    def failing_probe() -> str:
        raise RuntimeError("boom")

    service = HealthService({"problem": failing_probe})
    report = service.check()

    adapter = report.adapters["problem"]
    assert adapter.status is HealthStatus.UNAVAILABLE
    assert "RuntimeError" in (adapter.message or "")


def test_adapter_health_serialisation_handles_missing_latency() -> None:
    adapter = AdapterHealth(
        name="graph",
        status=HealthStatus.HEALTHY,
        latency_ms=float("nan"),
        message=None,
    )
    serialised = adapter.to_summary_dict()
    assert serialised["name"] == "graph"
    assert serialised["status"] == "healthy"
    assert serialised["message"] is None
    assert isinstance(serialised["latency_ms"], float)

    service = HealthService({"graph": lambda: None})
    report = service.check()
    with pytest.raises(KeyError):
        _ = report.adapters["missing"]
