"""Unit tests for the bootstrap middleware helpers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from theo.services.api.app.bootstrap.middleware import (
    configure_cors,
    get_security_dependencies,
    install_error_reporting,
    register_trace_handlers,
)
from theo.services.api.app.debug import ErrorReportingMiddleware
from theo.services.api.app.errors import TheoError
from theo.services.api.app.ingest.exceptions import UnsupportedSourceError


def test_configure_cors_adds_middleware():
    app = FastAPI()
    configure_cors(app, allow_origins=["https://example.test"])

    assert any(m.cls is CORSMiddleware for m in app.user_middleware)


def test_configure_cors_no_origins_skips_installation():
    app = FastAPI()
    configure_cors(app, allow_origins=[])

    assert not any(m.cls is CORSMiddleware for m in app.user_middleware)


def test_install_error_reporting_adds_middleware():
    app = FastAPI()
    install_error_reporting(app)

    assert any(m.cls is ErrorReportingMiddleware for m in app.user_middleware)


def test_register_trace_handlers_sets_handlers():
    app = FastAPI()
    register_trace_handlers(app)

    # HTTP middleware entry is inserted at the front of the stack
    assert any(m.cls.__name__ == "BaseHTTPMiddleware" for m in app.user_middleware)

    for exc_type in (HTTPException, TheoError, UnsupportedSourceError, RequestValidationError, Exception):
        assert exc_type in app.exception_handlers

    dependencies = get_security_dependencies()
    assert dependencies
