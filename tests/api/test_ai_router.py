import itertools

import pytest

from theo.services.api.app.ai.clients import GenerationError
from theo.services.api.app.ai.registry import LLMModel, LLMRegistry
from theo.services.api.app.ai.router import LLMRouterService, reset_router_state
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
    assert router.get_latency("slow") is not None
    assert router.get_latency("slow") > 1.0


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
