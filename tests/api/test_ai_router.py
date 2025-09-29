import itertools

from unittest.mock import Mock
import threading
import time
from concurrent.futures import ThreadPoolExecutor


import pytest

from theo.services.api.app.ai.clients import GenerationError
from theo.services.api.app.ai.registry import LLMModel, LLMRegistry
from theo.services.api.app.ai.router import (
    LLMRouterService,
    RoutedGeneration,
    reset_router_state,
)
from theo.services.api.app.ai import router as router_module


@pytest.fixture(autouse=True)
def _reset_router_state():
    reset_router_state()
    yield
    reset_router_state()


def _run_generation(router: LLMRouterService, workflow: str = "chat"):
    for candidate in router.iter_candidates(workflow):
        try:
            return router.execute_generation(
                workflow=workflow,
                model=candidate,
                prompt="hello",
            )
        except GenerationError:
            continue
    raise AssertionError("router failed to produce a generation")


def test_router_logs_warning_when_budget_projection_near_ceiling(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.6},
            routing={"spend_ceiling": 1.0, "weight": 5.0},
        ),
        make_default=True,
    )
    mock_logger = Mock()
    monkeypatch.setattr(router_module, "LOGGER", mock_logger)
    router = LLMRouterService(registry)

    with router._ledger.lock:  # type: ignore[attr-defined]
        router._ledger.spend["primary"] = 0.3  # type: ignore[attr-defined]

    result = router.execute_generation(workflow="chat", model=registry.models["primary"], prompt="hello")

    assert result.model.name == "primary"
    assert any("projected spend" in call.args[0] for call in mock_logger.warning.call_args_list)


def test_router_logs_warning_when_latency_projection_near_threshold(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.1},
            routing={"latency_threshold_ms": 100.0, "weight": 5.0},
        ),
        make_default=True,
    )
    mock_logger = Mock()
    monkeypatch.setattr(router_module, "LOGGER", mock_logger)
    router = LLMRouterService(registry)

    with router._ledger.lock:  # type: ignore[attr-defined]
        router._ledger.latency["primary"] = 90.0  # type: ignore[attr-defined]

    times = itertools.chain([0.0, 0.0], itertools.repeat(0.0))
    monkeypatch.setattr(router_module.time, "perf_counter", lambda: next(times))

    result = router.execute_generation(workflow="chat", model=registry.models["primary"], prompt="hello")

    assert result.model.name == "primary"
    assert any("recent latency" in call.args[0] for call in mock_logger.warning.call_args_list)


def test_router_logs_warning_when_budget_exceeded(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.1, "completion_tokens": 1.0},
            routing={"spend_ceiling": 1.0, "weight": 5.0},
        ),
        make_default=True,
    )
    mock_logger = Mock()
    monkeypatch.setattr(router_module, "LOGGER", mock_logger)
    router = LLMRouterService(registry)

    class _ExpensiveClient:
        def generate(self, **_: object) -> str:
            return "x" * 4000

    monkeypatch.setattr(registry.models["primary"], "build_client", lambda: _ExpensiveClient())

    with pytest.raises(GenerationError):
        router.execute_generation(workflow="chat", model=registry.models["primary"], prompt="hello")

    assert any("exceeded ceiling" in call.args[0] for call in mock_logger.warning.call_args_list)


def test_router_logs_warning_when_latency_exceeded(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            routing={"latency_threshold_ms": 50.0, "weight": 5.0},
        ),
        make_default=True,
    )
    mock_logger = Mock()
    monkeypatch.setattr(router_module, "LOGGER", mock_logger)
    router = LLMRouterService(registry)

    times = itertools.chain([0.0, 0.2], itertools.repeat(0.2))
    monkeypatch.setattr(router_module.time, "perf_counter", lambda: next(times))

    with pytest.raises(GenerationError):
        router.execute_generation(workflow="chat", model=registry.models["primary"], prompt="hello")

    assert any("latency" in call.args[0] and "exceeded" in call.args[0] for call in mock_logger.warning.call_args_list)


def test_router_respects_budget_and_falls_back():
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.6},
            routing={"spend_ceiling": 1.0, "weight": 10.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="backup",
            provider="echo",
            model="echo",
            config={"suffix": "[backup]"},
            pricing={"per_call": 0.4},
            routing={"weight": 1.0},
        )
    )
    router = LLMRouterService(registry)

    first = _run_generation(router)
    assert first.model.name == "primary"
    assert router.get_spend("primary") == pytest.approx(0.6)

    second = _run_generation(router)
    assert second.model.name == "backup"
    assert router.get_spend("primary") == pytest.approx(1.0)
    assert router.get_spend("backup") > 0.0


def test_router_latency_threshold_triggers_fallback(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="slow",
            provider="echo",
            model="echo",
            config={"suffix": "[slow]"},
            routing={"latency_threshold_ms": 1.0, "weight": 5.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="fast",
            provider="echo",
            model="echo",
            config={"suffix": "[fast]"},
            routing={"weight": 1.0},
        )
    )
    router = LLMRouterService(registry)

    times = itertools.cycle([0.0, 0.005, 0.02, 0.021])
    monkeypatch.setattr(router_module.time, "perf_counter", lambda: next(times))

    result = _run_generation(router)
    assert result.model.name == "fast"
    slow_latency = router.get_latency("slow")
    assert slow_latency is not None
    assert slow_latency > 1.0


def test_router_generation_error_when_ledger_prepopulated():
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={"suffix": "[primary]"},
            pricing={"per_call": 0.2},
            routing={
                "spend_ceiling": 1.0,
                "latency_threshold_ms": 10.0,
                "weight": 2.0,
            },

        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="secondary",
            provider="echo",
            model="echo",
            config={"suffix": "[secondary]"},
            pricing={"per_call": 0.2},
            routing={
                "spend_ceiling": 1.0,
                "latency_threshold_ms": 10.0,
                "weight": 1.0,
            },
        )
    )
    router = LLMRouterService(registry)

    with router._ledger.lock:  # type: ignore[attr-defined]
        for model in registry.models.values():
            router._ledger.spend[model.name] = 1.5  # type: ignore[attr-defined]
            router._ledger.latency[model.name] = 50.0  # type: ignore[attr-defined]

    model = registry.models["primary"]
    with pytest.raises(GenerationError):
        router.execute_generation(workflow="chat", model=model, prompt="hello")

    assert router.get_spend("primary") == pytest.approx(1.0)


def test_router_prefers_model_hint_and_falls_back(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="heavy",
            provider="echo",
            model="echo",
            config={"suffix": "[heavy]"},
            routing={"weight": 5.0},
        ),
        make_default=True,
    )
    registry.add_model(
        LLMModel(
            name="hinted",
            provider="echo",
            model="echo",
            config={"suffix": "[hinted]"},
            routing={"weight": 1.0},
        )
    )

    router = LLMRouterService(registry)

    candidates = router.iter_candidates("chat", model_hint="hinted")
    first = next(candidates)
    assert first.name == "hinted"

    class _FailingClient:
        def generate(self, **_: object) -> str:
            raise GenerationError("boom")

    # Force the hinted model to fail generation to confirm fallback order.
    monkeypatch.setattr(registry.models["hinted"], "build_client", lambda: _FailingClient())
    with pytest.raises(GenerationError):
        router.execute_generation(workflow="chat", model=first, prompt="hello")

    fallback = next(candidates)
    assert fallback.name == "heavy"


def test_router_reuses_cache_entry(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="cached",
            provider="echo",
            model="echo",
            config={},
            pricing={"per_call": 0.5},
            routing={
                "cache_enabled": True,
                "cache_ttl_seconds": 120,
                "cache_max_entries": 8,
                "weight": 1.0,
            },
        ),
        make_default=True,
    )

    router = LLMRouterService(registry)

    call_count = 0

    class _CountingClient:
        def generate(self, **_: object) -> str:
            nonlocal call_count
            call_count += 1
            return "cached-output"

    monkeypatch.setattr(registry.models["cached"], "build_client", lambda: _CountingClient())

    model = registry.get()
    first = router.execute_generation(workflow="chat", model=model, prompt="hello")
    second = router.execute_generation(workflow="chat", model=model, prompt="hello")

    assert call_count == 1
    assert second.output == first.output
    assert router.get_spend("cached") == pytest.approx(first.cost)


def test_router_deduplicates_inflight_requests(monkeypatch):
    registry = LLMRegistry()
    registry.add_model(
        LLMModel(
            name="primary",
            provider="echo",
            model="echo",
            config={},
            pricing={"per_call": 0.3},
            routing={"weight": 1.0},
        ),
        make_default=True,
    )

    router = LLMRouterService(registry)
    model = registry.get()

    call_count = 0
    call_lock = threading.Lock()

    class _SlowClient:
        def generate(self, **_: object) -> str:
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.05)
            return "shared-output"

    monkeypatch.setattr(model, "build_client", lambda: _SlowClient())

    start_barrier = threading.Barrier(3)

    def _invoke() -> RoutedGeneration:
        start_barrier.wait()
        return router.execute_generation(workflow="chat", model=model, prompt="simultaneous")

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(_invoke) for _ in range(3)]
        results = [future.result() for future in futures]

    assert call_count == 1
    assert {result.output for result in results} == {"shared-output"}
    assert router.get_spend("primary") == pytest.approx(results[0].cost)

