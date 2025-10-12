"""Comprehensive security tests for Agent Confinement Framework."""

from __future__ import annotations

import pytest
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import HTTPException

from mcp_server import schemas
from mcp_server.security import (
    WriteSecurityError,
    reset_write_security_policy,
    reset_read_security_policy,
    get_write_security_policy,
    get_read_security_policy,
)
from mcp_server.validators import ValidationError, validate_end_user_id, validate_query
from mcp_server.tools import read, write


@contextmanager
def _fake_session_scope():
    yield SimpleNamespace()


@pytest.fixture(autouse=True)
def reset_policies(monkeypatch):
    """Reset all security policies between tests."""
    reset_write_security_policy()
    reset_read_security_policy()
    monkeypatch.delenv("MCP_WRITE_ALLOWLIST", raising=False)
    monkeypatch.delenv("MCP_WRITE_RATE_LIMITS", raising=False)
    monkeypatch.delenv("MCP_READ_RATE_LIMITS", raising=False)
    monkeypatch.setattr(read, "_session_scope", _fake_session_scope)
    monkeypatch.setattr(write, "_session_scope", _fake_session_scope)
    yield
    reset_write_security_policy()
    reset_read_security_policy()


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ============================================================================
# HEADER VALIDATION TESTS
# ============================================================================


def test_end_user_id_validation_rejects_empty():
    """Empty end_user_id should be rejected."""
    with pytest.raises(ValidationError) as exc:
        validate_end_user_id("")
    assert "cannot be empty" in str(exc.value.detail)


def test_end_user_id_validation_rejects_invalid_chars():
    """end_user_id with invalid characters should be rejected."""
    with pytest.raises(ValidationError) as exc:
        validate_end_user_id("user<script>alert('xss')</script>")
    assert "invalid characters" in str(exc.value.detail).lower()


def test_end_user_id_validation_rejects_too_long():
    """end_user_id exceeding max length should be rejected."""
    long_id = "a" * 300
    with pytest.raises(ValidationError) as exc:
        validate_end_user_id(long_id)
    assert "maximum length" in str(exc.value.detail).lower()


def test_end_user_id_validation_accepts_valid():
    """Valid end_user_id formats should be accepted."""
    valid_ids = [
        "user-123",
        "user.name@example.com",
        "tenant_user_456",
        "abc123",
    ]
    for user_id in valid_ids:
        result = validate_end_user_id(user_id)
        assert result == user_id


# ============================================================================
# INPUT VALIDATION TESTS
# ============================================================================


def test_query_validation_rejects_script_tags():
    """Queries with script tags should be rejected."""
    malicious_query = "search <script>alert('xss')</script>"
    with pytest.raises(ValidationError) as exc:
        validate_query(malicious_query)
    assert "security risk" in str(exc.value.detail).lower()


def test_query_validation_rejects_javascript_protocol():
    """Queries with javascript: protocol should be rejected."""
    malicious_query = "javascript:void(0)"
    with pytest.raises(ValidationError) as exc:
        validate_query(malicious_query)
    assert "security risk" in str(exc.value.detail).lower()


def test_query_validation_rejects_path_traversal():
    """Queries with path traversal patterns should be rejected."""
    malicious_query = "../../etc/passwd"
    with pytest.raises(ValidationError) as exc:
        validate_query(malicious_query)
    assert "security risk" in str(exc.value.detail).lower()


def test_query_validation_rejects_excessive_length():
    """Queries exceeding max length should be rejected."""
    long_query = "a" * 3000
    with pytest.raises(ValidationError) as exc:
        validate_query(long_query)
    assert "maximum length" in str(exc.value.detail).lower()


def test_query_validation_accepts_normal_queries():
    """Normal theological queries should be accepted."""
    valid_queries = [
        "doctrine of justification",
        "Romans 8:28 commentary",
        "What is the Trinity?",
        "Calvin's view on predestination",
    ]
    for query in valid_queries:
        validate_query(query)  # Should not raise


# ============================================================================
# RATE LIMITING TESTS - READ OPERATIONS
# ============================================================================


@pytest.mark.anyio("asyncio")
async def test_read_rate_limiting_enforced(monkeypatch):
    """Read operations should enforce rate limits when configured."""
    monkeypatch.setenv("MCP_READ_RATE_LIMITS", "search_library=2")
    reset_read_security_policy()

    # Mock search results
    monkeypatch.setattr(
        read,
        "hybrid_search",
        lambda session, request: [],
    )

    request = schemas.SearchLibraryRequest(
        request_id="req-1",
        query="test query",
    )

    # First two requests should succeed
    await read.search_library(request, end_user_id="user-test")
    await read.search_library(request, end_user_id="user-test")

    # Third request should be rate limited
    with pytest.raises(HTTPException) as exc:
        await read.search_library(request, end_user_id="user-test")
    assert exc.value.status_code == 429


@pytest.mark.anyio("asyncio")
async def test_read_rate_limiting_per_user(monkeypatch):
    """Read rate limits should be enforced per user."""
    monkeypatch.setenv("MCP_READ_RATE_LIMITS", "search_library=1")
    reset_read_security_policy()

    monkeypatch.setattr(
        read,
        "hybrid_search",
        lambda session, request: [],
    )

    request = schemas.SearchLibraryRequest(
        request_id="req-1",
        query="test query",
    )

    # User 1 exhausts their limit
    await read.search_library(request, end_user_id="user-1")

    # User 1 should be rate limited
    with pytest.raises(HTTPException) as exc:
        await read.search_library(request, end_user_id="user-1")
    assert exc.value.status_code == 429

    # User 2 should still be allowed
    await read.search_library(request, end_user_id="user-2")


# ============================================================================
# RATE LIMITING TESTS - WRITE OPERATIONS
# ============================================================================


@pytest.mark.anyio("asyncio")
async def test_write_rate_limiting_blocks_excessive_requests(monkeypatch):
    """Write operations should enforce stricter rate limits."""
    monkeypatch.setenv("MCP_WRITE_RATE_LIMITS", "note_write=1")
    reset_write_security_policy()

    monkeypatch.setattr(
        write,
        "create_research_note",
        lambda session, **_: SimpleNamespace(id="note-1"),
    )

    request = schemas.NoteWriteRequest(
        request_id="req-1",
        osis="John.1.1",
        body="Test note",
        commit=True,
    )

    # First request succeeds
    await write.note_write(request, end_user_id="user-1")

    # Second request is rate limited
    with pytest.raises(HTTPException) as exc:
        await write.note_write(request, end_user_id="user-1")
    assert exc.value.status_code == 429


# ============================================================================
# ALLOWLIST TESTS
# ============================================================================


@pytest.mark.anyio("asyncio")
async def test_allowlist_blocks_unauthorized_writes(monkeypatch):
    """Write operations should enforce allowlists."""
    monkeypatch.setenv("MCP_WRITE_ALLOWLIST", "note_write=authorized-tenant")
    reset_write_security_policy()

    request = schemas.NoteWriteRequest(
        request_id="req-1",
        osis="John.1.1",
        body="Test note",
        commit=True,
    )

    # Unauthorized tenant is blocked
    with pytest.raises(HTTPException) as exc:
        await write.note_write(
            request,
            end_user_id="user-1",
            tenant_id="unauthorized-tenant",
        )
    assert exc.value.status_code == 403


@pytest.mark.anyio("asyncio")
async def test_allowlist_permits_authorized_writes(monkeypatch):
    """Allowlisted identities should be permitted to write."""
    monkeypatch.setenv("MCP_WRITE_ALLOWLIST", "note_write=authorized-tenant")
    reset_write_security_policy()

    monkeypatch.setattr(
        write,
        "create_research_note",
        lambda session, **_: SimpleNamespace(id="note-1"),
    )

    request = schemas.NoteWriteRequest(
        request_id="req-1",
        osis="John.1.1",
        body="Test note",
        commit=True,
    )

    # Authorized tenant is allowed
    response = await write.note_write(
        request,
        end_user_id="user-1",
        tenant_id="authorized-tenant",
    )
    assert response.commit is True
    assert response.note_id == "note-1"


# ============================================================================
# SECURITY MONITORING TESTS
# ============================================================================


def test_security_policy_tracks_violations(monkeypatch):
    """Security policy should track violation events."""
    monkeypatch.setenv("MCP_WRITE_ALLOWLIST", "note_write=allowed")
    policy = get_write_security_policy()

    # Trigger access denied
    try:
        policy.ensure_allowed("note_write", True, "blocked-tenant", "user-1")
    except WriteSecurityError:
        pass

    metrics = policy.get_security_metrics()
    assert "access_denied:note_write" in metrics
    assert metrics["access_denied:note_write"] >= 1


def test_security_policy_tracks_rate_limit_violations(monkeypatch):
    """Security policy should track rate limit violations."""
    monkeypatch.setenv("MCP_WRITE_RATE_LIMITS", "note_write=0")
    policy = get_write_security_policy()

    # Trigger rate limit
    try:
        policy.enforce_rate_limit("note_write", True, None, "user-1")
    except WriteSecurityError:
        pass

    metrics = policy.get_security_metrics()
    assert "rate_limit_exceeded:note_write" in metrics


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.anyio("asyncio")
async def test_end_to_end_read_with_validation(monkeypatch):
    """End-to-end read operation with full validation."""
    monkeypatch.setattr(
        read,
        "hybrid_search",
        lambda session, request: [],
    )

    request = schemas.SearchLibraryRequest(
        request_id="req-1",
        query="What is grace?",
        filters={"theological_tradition": "reformed"},
    )

    response = await read.search_library(
        request,
        end_user_id="user-test@example.com",
    )

    assert response.request_id == "req-1"
    assert response.results == []


@pytest.mark.anyio("asyncio")
async def test_end_to_end_write_with_validation(monkeypatch):
    """End-to-end write operation with full validation."""
    monkeypatch.setattr(
        write,
        "generate_research_note_preview",
        lambda session, **_: SimpleNamespace(
            osis="Romans.3.23",
            title="Sin",
            stance="neutral",
            claim_type="doctrine",
            tags=["sin", "doctrine"],
            body="All have sinned",
        ),
    )

    request = schemas.NoteWriteRequest(
        request_id="req-1",
        osis="Romans.3.23",
        body="All have sinned and fall short of the glory of God",
        title="Universal Sinfulness",
        tags=["sin", "doctrine"],
    )

    response = await write.note_write(
        request,
        end_user_id="user-test@example.com",
    )

    assert response.commit is False
    assert response.status == "preview"
    assert response.preview is not None


@pytest.mark.anyio("asyncio")
async def test_malicious_input_blocked_at_entry(monkeypatch):
    """Malicious input should be blocked before reaching business logic."""
    malicious_request = schemas.SearchLibraryRequest(
        request_id="req-evil",
        query="<script>alert('xss')</script>",
    )

    # Should fail validation before hitting business logic
    with pytest.raises(HTTPException) as exc:
        await read.search_library(
            malicious_request,
            end_user_id="attacker",
        )
    assert exc.value.status_code == 422  # Unprocessable Entity


# ============================================================================
# OSIS VALIDATION TESTS
# ============================================================================


def test_osis_validation_accepts_valid_references():
    """Valid OSIS references should be accepted."""
    from mcp_server.validators import validate_osis_reference

    valid_refs = [
        "John.3.16",
        "Gen.1.1",
        "Ps.23.1",
        "Rom.8.28",
        "Rev.22.21",
    ]
    for ref in valid_refs:
        validate_osis_reference(ref)  # Should not raise


def test_osis_validation_rejects_invalid_format():
    """Invalid OSIS format should be rejected."""
    from mcp_server.validators import validate_osis_reference

    invalid_refs = [
        "John 3:16",  # Wrong separator
        "Book$Chapter.Verse",  # Invalid characters
        "<script>alert('xss')</script>",  # XSS attempt
        "../../../etc/passwd",  # Path traversal
    ]
    for ref in invalid_refs:
        with pytest.raises(ValidationError):
            validate_osis_reference(ref)
