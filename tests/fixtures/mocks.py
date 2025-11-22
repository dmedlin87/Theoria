"""Session-wide mocks for expensive external integrations."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def optimize_mocks() -> None:
    """Provide deterministic mocks for heavy external dependencies."""

    with ExitStack() as stack:
        try:
            async_client_patch = stack.enter_context(patch("httpx.AsyncClient"))
        except ModuleNotFoundError:
            async_client_patch = None
        else:
            async_client = AsyncMock()
            context_client = AsyncMock()
            response_mock = AsyncMock()
            response_mock.status_code = 200
            context_client.get.return_value = response_mock
            async_client.__aenter__.return_value = context_client
            async_client.__aexit__.return_value = False
            async_client.get.return_value = response_mock
            async_client_patch.return_value = async_client

        try:
            from celery import Celery as CeleryClass
        except ModuleNotFoundError:
            celery_init_patch = None
        else:
            original_init = CeleryClass.__init__

            def _patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                original_init(self, *args, **kwargs)
                conf = getattr(self, "conf", None)
                if conf is not None:
                    conf.task_always_eager = True
                    conf.task_ignore_result = True
                    if hasattr(conf, "task_store_eager_result"):
                        conf.task_store_eager_result = False

            celery_init_patch = stack.enter_context(
                patch.object(CeleryClass, "__init__", _patched_init)
            )

        yield
