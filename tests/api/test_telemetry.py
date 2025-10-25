from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from theo.application.facades import telemetry as telemetry_facade
from theo.services.api.app.adapters.telemetry import ApiTelemetryProvider


@pytest.fixture(autouse=True)
def disable_prometheus(monkeypatch):
    monkeypatch.setattr("theo.services.api.app.adapters.telemetry.Counter", None)
    monkeypatch.setattr("theo.services.api.app.adapters.telemetry.Histogram", None)


@pytest.mark.parametrize(
    "value",
    [
        {"labels": ["a", "b"]},
        {"scores": {"verse": 0.9, "sermon": 0.8}},
    ],
)
def test_repro_workflow_context_dict_serialization(value: object, monkeypatch) -> None:
    monkeypatch.setattr(telemetry_facade, "_provider", ApiTelemetryProvider())
    span = MagicMock()

    telemetry_facade.set_span_attribute(span, "workflow.context", value)

    span.set_attribute.assert_called_once_with("workflow.context", value)


def test_instrument_workflow_records_metrics(monkeypatch):
    provider = ApiTelemetryProvider()
    mock_span = MagicMock()

    class _FakeContextManager:
        def __enter__(self):
            return mock_span

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeTracer:
        def start_as_current_span(self, name):
            self.name = name
            return _FakeContextManager()

    fake_tracer = _FakeTracer()
    monkeypatch.setattr(provider, "_get_tracer", lambda name: fake_tracer)

    latency_metric = MagicMock()
    latency_metric.labels.return_value.observe = MagicMock()
    runs_metric = MagicMock()
    runs_metric.labels.return_value.inc = MagicMock()
    provider._workflow_latency = latency_metric
    provider._workflow_runs = runs_metric

    with provider.instrument_workflow("demo", foo="bar"):
        pass

    assert fake_tracer.name == "workflow.demo"
    mock_span.set_attribute.assert_any_call("workflow.foo", "bar")
    latency_metric.labels.assert_called_with(workflow="demo")
    latency_metric.labels.return_value.observe.assert_called()
    runs_metric.labels.assert_called_with(workflow="demo", status="success")
    runs_metric.labels.return_value.inc.assert_called_with()


def test_record_counter_sanitises_metric_names(monkeypatch):
    provider = ApiTelemetryProvider()
    metric = MagicMock()
    metric.labels.return_value.inc = MagicMock()

    captured: dict[str, object] = {}

    def fake_get_counter(name, labels):
        captured["name"] = name
        captured["labels"] = labels
        return metric

    monkeypatch.setattr(provider, "_get_counter_metric", fake_get_counter)

    provider.record_counter("rag.cache.events", labels={"status": "hit"})

    assert captured["name"] == "rag_cache_events"
    assert captured["labels"] == ("status",)
    metric.labels.assert_called_with(status="hit")
    metric.labels.return_value.inc.assert_called_with(1.0)
