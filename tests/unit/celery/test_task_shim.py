"""Unit tests for the in-repo Celery shims."""

from __future__ import annotations

import logging
import os
import sys
from importlib import util as importlib_util
from types import ModuleType, SimpleNamespace

import pytest

SHIM_PACKAGE = "celery_test_shim"
CELERY_ROOT = os.fspath(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "celery")
    )
)


def _register_module(module_name: str, relative_path: str) -> ModuleType:
    module_path = os.path.join(CELERY_ROOT, *relative_path.split("/"))
    spec = importlib_util.spec_from_file_location(module_name, module_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load Celery shim module {module_name}")
    module = importlib_util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


if SHIM_PACKAGE not in sys.modules:
    package = ModuleType(SHIM_PACKAGE)
    package.__path__ = [CELERY_ROOT]  # type: ignore[attr-defined]
    sys.modules[SHIM_PACKAGE] = package
    _register_module(f"{SHIM_PACKAGE}.exceptions", "exceptions.py")
    _register_module(f"{SHIM_PACKAGE}.schedules", "schedules.py")
    _register_module(f"{SHIM_PACKAGE}.utils", "utils/__init__.py")
    _register_module(f"{SHIM_PACKAGE}.utils.log", "utils/log.py")
    _register_module(f"{SHIM_PACKAGE}.app", "app/__init__.py")
    task_module = _register_module(f"{SHIM_PACKAGE}.app.task", "app/task.py")
else:
    task_module = sys.modules[f"{SHIM_PACKAGE}.app.task"]

Task = task_module.Task  # type: ignore[attr-defined]
CeleryRetry = sys.modules[f"{SHIM_PACKAGE}.exceptions"].Retry  # type: ignore[attr-defined]
crontab = sys.modules[f"{SHIM_PACKAGE}.schedules"].crontab  # type: ignore[attr-defined]
get_task_logger = sys.modules[f"{SHIM_PACKAGE}.utils.log"].get_task_logger  # type: ignore[attr-defined]


def _adder(a: int, b: int) -> int:
    return a + b


def test_task_apply_records_request_context() -> None:
    task = Task(_adder, app=None, name="adder")

    result = task.apply(args=(2,), kwargs={"b": 5})

    assert result.result == 7
    assert task.request.args == (2,)
    assert task.request.kwargs == {"b": 5}
    assert task.request.retries == 0


def test_task_apply_async_and_delay_are_aliases() -> None:
    observed: list[tuple[tuple[int, ...], dict[str, int]]] = []

    def capture(*args: int, **kwargs: int) -> tuple[tuple[int, ...], dict[str, int]]:
        observed.append((args, kwargs))
        return args, kwargs

    task = Task(capture, app=None, name="capture")

    async_result = task.apply_async(args=(1, 2), kwargs={"c": 3})
    delay_result = task.delay(args=(4,), kwargs={"d": 5})

    assert async_result.result == ((1, 2), {"c": 3})
    assert delay_result.result == ((4,), {"d": 5})
    # Ensure the callable was invoked each time with the provided payloads.
    assert observed == [((1, 2), {"c": 3}), ((4,), {"d": 5})]


def test_task_run_bind_true_exposes_task_instance() -> None:
    captured = {}

    def bound(task: Task, value: int) -> int:
        captured["called"] = True
        task.request.retries += 1
        return value * 2

    task = Task(bound, app=None, name="bound", bind=True)

    assert task.run(6) == 12
    assert captured["called"] is True
    assert task.request.retries == 1


def test_task_retry_raises_celery_retry_exception() -> None:
    task = Task(lambda: None, app=None, name="noop")
    original_exc = ValueError("boom")

    with pytest.raises(CeleryRetry) as exc_info:
        task.retry(exc=original_exc, countdown=3.5)

    assert exc_info.value.exc is original_exc
    assert exc_info.value.when == 3.5


def test_task_signature_from_request_merges_request_values() -> None:
    task = Task(lambda: None, app=None, name="signature")
    request = SimpleNamespace(args=(1,), kwargs={"a": 2}, retries=2)

    signature = task.signature_from_request(
        request,
        args=None,
        kwargs=None,
        countdown=10,
        eta=20,
    )

    assert signature.args == (1,)
    assert signature.kwargs == {"a": 2}
    assert signature.countdown == 10
    assert signature.eta == 20
    assert signature.retries == 2


def test_retry_exception_tracks_metadata() -> None:
    underlying = RuntimeError("failure")
    retry = CeleryRetry(
        "retry",
        exc=underlying,
        when=9.5,
        is_eager=True,
        sig="signature",
    )

    assert str(retry) == "retry"
    assert retry.exc is underlying
    assert retry.when == 9.5
    assert retry.is_eager is True
    assert retry.sig == "signature"


def test_crontab_preserves_args_and_kwargs() -> None:
    schedule = crontab("0", "12", tz="UTC", day_of_week="mon")

    assert schedule.args == ("0", "12")
    assert schedule.kwargs == {"tz": "UTC", "day_of_week": "mon"}
    assert schedule() == {"args": ("0", "12"), "kwargs": {"tz": "UTC", "day_of_week": "mon"}}


def test_get_task_logger_delegates_to_logging_module() -> None:
    logger_name = "celery.test"
    logger = get_task_logger(logger_name)

    assert logger is logging.getLogger(logger_name)
    logger.debug("ensures logger works without raising")
