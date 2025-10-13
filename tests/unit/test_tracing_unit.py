import pytest

from theo.services.api.app import tracing


class FakeContext:
    def __init__(self, trace_id=None, span_id=None, trace_flags=None):
        self.trace_id = trace_id
        self.span_id = span_id
        self.trace_flags = trace_flags


class FakeSpan:
    def __init__(self, context):
        self._context = context

    def get_span_context(self):
        return self._context


@pytest.fixture
def set_get_current_span():
    original = tracing._GET_CURRENT_SPAN

    def setter(context):
        fake_span = FakeSpan(context)

        def _fake_get_current_span():
            return fake_span

        tracing._GET_CURRENT_SPAN = _fake_get_current_span
        return fake_span

    yield setter
    tracing._GET_CURRENT_SPAN = original


def test_trace_helpers_format_expected_values(set_get_current_span):
    context = FakeContext(
        trace_id=int("1234567890abcdef1234567890abcdef", 16),
        span_id=int("89abcdef01234567", 16),
        trace_flags=1,
    )
    set_get_current_span(context)

    expected_trace_id = "1234567890abcdef1234567890abcdef"
    expected_traceparent = "00-1234567890abcdef1234567890abcdef-89abcdef01234567-01"

    assert tracing.get_current_trace_id() == expected_trace_id
    assert tracing.get_current_traceparent() == expected_traceparent
    assert tracing.get_current_trace_headers() == {
        tracing.TRACEPARENT_HEADER_NAME: expected_traceparent,
        tracing.TRACE_ID_HEADER_NAME: expected_trace_id,
    }


def test_trace_helpers_missing_values_return_empty_results(set_get_current_span):
    context = FakeContext(trace_id=0, span_id=0, trace_flags=0)
    set_get_current_span(context)

    assert tracing.get_current_trace_id() is None
    assert tracing.get_current_traceparent() is None
    assert tracing.get_current_trace_headers() == {}


def test_trace_helpers_invalid_values_return_empty_results(set_get_current_span):
    context = FakeContext(trace_id="not-a-number", span_id="also-bad", trace_flags="??")
    set_get_current_span(context)

    assert tracing.get_current_trace_id() is None
    assert tracing.get_current_traceparent() is None
    assert tracing.get_current_trace_headers() == {}
