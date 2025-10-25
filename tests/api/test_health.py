from __future__ import annotations

from fastapi.testclient import TestClient

from theo.services.api.app.main import app

from theo.services.api.app.infra import health as health_module


def test_health_service_propagates_degraded_status() -> None:
    def healthy_probe() -> str:
        return "OK"

    def degraded_probe() -> str:
        raise health_module.HealthProbeError(
            "Cache warming in progress", status=health_module.HealthStatus.DEGRADED
        )

    service = health_module.HealthService(
        {
            "database": healthy_probe,
            "redis": degraded_probe,
        }
    )

    report = service.check()

    assert report.status is health_module.HealthStatus.DEGRADED
    redis_health = report.adapters["redis"]
    assert redis_health.status is health_module.HealthStatus.DEGRADED
    assert "Cache warming" in (redis_health.message or "")


def test_health_endpoint_reports_worst_status(monkeypatch) -> None:
    def healthy_probe() -> str:
        return "OK"

    def unavailable_probe() -> str:
        raise health_module.HealthProbeError(
            "Redis unreachable", status=health_module.HealthStatus.UNAVAILABLE
        )

    monkeypatch.setattr(
        health_module,
        "DEFAULT_PROBES",
        {
            "database": healthy_probe,
            "redis": unavailable_probe,
            "embeddings": healthy_probe,
            "graph": healthy_probe,
        },
    )

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        summary = response.json()
        assert summary["status"] == health_module.HealthStatus.UNAVAILABLE.value
        assert "redis" in summary["message"].lower()

        detail_response = client.get("/health/detail")
        assert detail_response.status_code == 200
        payload = detail_response.json()
        adapters = {entry["name"]: entry for entry in payload["adapters"]}
        assert adapters["redis"]["status"] == health_module.HealthStatus.UNAVAILABLE.value
        assert adapters["redis"]["message"] == "Redis unreachable"
