from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from theo.services.api.app import telemetry


@pytest.mark.parametrize(
    "value",
    [
        {"labels": ["a", "b"]},
        {"scores": {"verse": 0.9, "sermon": 0.8}},
    ],
)
def test_repro_workflow_context_dict_serialization(value: object) -> None:
    span = MagicMock()

    telemetry.set_span_attribute(span, "workflow.context", value)

    span.set_attribute.assert_called_once_with("workflow.context", value)
