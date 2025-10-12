# Agent Confinement Framework

## Overview

The Agent Confinement Framework ensures that AI agents accessing Theo Engine through the MCP (Model Context Protocol) server operate within strict security boundaries. This framework enforces authentication, input validation, rate limiting, and content filtering to prevent abuse while enabling safe theological research capabilities.

## Architecture

### Security Layers

```text
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Entry Point Validation                             │
│ - Header validation (end_user_id, tenant_id)                │
│ - Input sanitization and length checks                       │
│ - Injection pattern detection                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Rate Limiting & Access Control                     │
│ - Per-user rate limiting (read ops)                         │
│ - Per-tenant rate limiting (write ops)                      │
│ - Allowlist enforcement                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Business Logic                                     │
│ - Database session management                                │
│ - Core service delegation                                    │
│ - OpenTelemetry instrumentation                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: RAG Guardrails (Generative Workflows)             │
│ - Citation grounding validation                              │
│ - Theological tradition filtering                            │
│ - Content safety scanning                                    │
│ - Output validation                                          │
└─────────────────────────────────────────────────────────────┘
```

## Security Components

### 1. Input Validation (`mcp_server/validators.py`)

**Purpose:** Sanitize and validate all incoming data before processing.

**Validations:**

- **Header validation:** Ensures `X-End-User-Id`, `X-Tenant-Id`, and `X-Idempotency-Key` conform to safe patterns
- **Query validation:** Checks length, detects injection patterns (XSS, SQL, path traversal)
- **OSIS reference validation:** Ensures biblical references follow proper format
- **Body text validation:** Validates research note content for safety
- **Array length validation:** Prevents resource exhaustion attacks

**Injection Patterns Detected:**

- Script tags (`<script>`, `<iframe>`)
- JavaScript protocol (`javascript:`)
- Event handlers (`onclick=`, `onload=`)
- Path traversal (`../`, `..\\`)
- Eval functions

**Limits:**

- Query: 2,000 characters
- Body text: 50,000 characters
- Filters: 20 entries max
- Arrays: 100 items max
- Headers: 256 characters max

### 2. Rate Limiting

**Read Operations (`MCP_READ_RATE_LIMITS`):**

- Per-user rate limiting
- Configurable per-tool limits
- Sliding window (60 seconds default)
- Example: `MCP_READ_RATE_LIMITS="search_library=100;aggregate_verses=50"`

**Write Operations (`MCP_WRITE_RATE_LIMITS`):**

- Per-tenant or per-user rate limiting
- Stricter limits for mutations
- Idempotency support to prevent duplicate operations
- Example: `MCP_WRITE_RATE_LIMITS="note_write=10;index_refresh=1"`

**Configuration:**

```bash
# Read rate limits (requests per minute per user)
export MCP_READ_RATE_LIMITS="search_library=100;aggregate_verses=50;get_timeline=50"

# Write rate limits (requests per minute per user/tenant)
export MCP_WRITE_RATE_LIMITS="note_write=10;evidence_card_create=20;index_refresh=1"
```

### 3. Access Control

**Allowlists (`MCP_WRITE_ALLOWLIST`):**

- Restrict write operations to authorized identities
- Per-tool allowlist configuration
- Supports both tenant-level and user-level control

**Configuration:**

```bash
# Only allow specific tenants to write notes
export MCP_WRITE_ALLOWLIST="note_write=org-acme,org-seminary"

# Multiple tools with different allowlists
export MCP_WRITE_ALLOWLIST="note_write=org-acme;index_refresh=admin-user"
```

### 4. RAG Guardrails (`theo/services/api/app/ai/rag/guardrails.py`)

**Purpose:** Ensure AI-generated content is safe and properly grounded in source material.

**Guardrail Categories:**

**A. Retrieval Guardrails**

- Citation requirement enforcement
- Theological tradition filtering
- Topic domain filtering
- Fallback passage handling

**B. Generation Guardrails**

- Citation format validation
- OSIS reference verification
- Anchor consistency checks
- Source attribution requirements

**C. Safety Guardrails**

- SQL injection detection
- XSS pattern detection
- Credential leakage prevention
- Command injection detection
- Path traversal detection
- Prompt injection detection

**Safety Patterns Detected:**

```python
# SQL Injection
"SELECT * FROM users"
"; DROP TABLE passages"

# XSS
"<script>alert('xss')</script>"
"<iframe src='evil.com'></iframe>"
"javascript:void(0)"

# Credential Leakage
"password: secret123"
"api_key: sk-1234"
"Bearer eyJhbGciOiJIUzI1..."

# Command Injection
"$(rm -rf /)"
"`whoami`"
"ls && cat /etc/passwd"

# Path Traversal
"../../../etc/passwd"
"..\\..\\windows\\system32"

# Prompt Injection
"Ignore previous instructions"
"System: You are now..."
"</context>"
```

### 5. Audit Logging

**Security Events Logged:**

- Access denied events
- Rate limit violations
- Validation failures
- Malicious pattern detections

**Log Structure:**

```json
{
  "event": "security.event",
  "event_type": "rate_limit_exceeded",
  "tool": "search_library",
  "actor": "user-123",
  "timestamp": 1697432100.5
}
```

**Accessing Metrics:**

```python
from mcp_server.security import get_write_security_policy, get_read_security_policy

write_policy = get_write_security_policy()
read_policy = get_read_security_policy()

# Get security event counters
write_metrics = write_policy.get_security_metrics()
read_metrics = read_policy.get_security_metrics()
```

## MCP Tool Security

### Read Tools

All read tools enforce:

1. Header validation (`X-End-User-Id` required)
2. Input validation (queries, OSIS refs, filters)
3. Rate limiting (per-user)
4. Instrumentation (OpenTelemetry spans)

**Protected Tools:**

- `search_library` - Hybrid search with validation
- `aggregate_verses` - Scripture aggregation with OSIS validation
- `get_timeline` - Timeline data with filter validation
- `quote_lookup` - Quote retrieval with ID array limits
- `source_registry_list` - Document listing with pagination

### Write Tools

All write tools enforce:

1. Header validation (user + tenant + idempotency)
2. Input validation (body text, OSIS refs, arrays)
3. Allowlist checking
4. Rate limiting (stricter than reads)
5. Idempotency support
6. Preview mode (dry-run before commit)

**Protected Tools:**

- `note_write` - Research note creation with theological content validation
- `evidence_card_create` - Evidence card creation with claim validation
- `index_refresh` - Background job queueing with admin restrictions

## Testing

### Security Test Coverage

**Test File: `tests/mcp_tools/test_security_confinement.py`**

- Header validation (valid/invalid user IDs)
- Input validation (injection patterns, length limits)
- Read rate limiting (per-user enforcement)
- Write rate limiting (per-tenant enforcement)
- Allowlist enforcement
- Security metrics tracking
- End-to-end integration tests

**Test File: `tests/api/test_rag_guardrails_enhanced.py`**

- SQL injection detection
- XSS pattern detection
- Credential leakage detection
- Command injection detection
- Path traversal detection
- Prompt injection detection
- Safe content validation

### Running Security Tests

```bash
# Run all security tests
pytest tests/mcp_tools/test_security_confinement.py -v

# Run RAG guardrail tests
pytest tests/api/test_rag_guardrails_enhanced.py -v

# Run with coverage
pytest tests/mcp_tools/test_security_confinement.py --cov=mcp_server --cov-report=html
```

## Deployment Configuration

### Production Environment

```bash
# Enable MCP tools
export MCP_TOOLS_ENABLED=true

# Configure rate limits (conservative)
export MCP_READ_RATE_LIMITS="search_library=50;aggregate_verses=30;get_timeline=30;quote_lookup=40;source_registry_list=20"
export MCP_WRITE_RATE_LIMITS="note_write=5;evidence_card_create=10;index_refresh=1"

# Configure allowlists (restrict writes)
export MCP_WRITE_ALLOWLIST="note_write=org-seminary,org-ministry;evidence_card_create=org-seminary;index_refresh=admin-user"

# Schema base URL
export MCP_SCHEMA_BASE_URL="https://theoengine.dev/mcp/schemas"
```

### Development Environment

```bash
# Enable MCP tools
export MCP_TOOLS_ENABLED=true

# More permissive rate limits for testing
export MCP_READ_RATE_LIMITS="search_library=1000;aggregate_verses=500"
export MCP_WRITE_RATE_LIMITS="note_write=100"

# No allowlists in dev
unset MCP_WRITE_ALLOWLIST
```

## Monitoring

### Key Metrics to Monitor

1. **Rate Limit Violations:**
   - `rate_limit_exceeded:{tool}` - Indicates potential abuse
   - Alert threshold: >100 per hour per tool

2. **Access Denied Events:**
   - `access_denied:{tool}` - Unauthorized access attempts
   - Alert threshold: >10 per hour per tool

3. **Validation Failures:**
   - Track 422 HTTP responses
   - Alert threshold: >50 per hour

4. **Guardrail Violations:**
   - Safety pattern detections in logs
   - Alert threshold: Any occurrence

### Recommended Alerts

```yaml
# Example alert configuration
alerts:
  - name: "High Rate Limit Violations"
    condition: "rate_limit_exceeded > 100/hour"
    severity: "warning"
    
  - name: "Access Denied Spike"
    condition: "access_denied > 10/hour"
    severity: "critical"
    
  - name: "Guardrail Safety Violation"
    condition: "safety_pattern_detected > 0"
    severity: "critical"
    action: "immediate_investigation"
```

## Security Best Practices

### For Operators

1. **Always enable rate limiting in production**
2. **Use allowlists for write operations**
3. **Monitor security event metrics**
4. **Rotate idempotency cache periodically**
5. **Review audit logs for anomalies**
6. **Keep guardrail patterns updated**

### For Developers

1. **Never bypass validation layers**
2. **Always validate at entry points**
3. **Use parameterized queries**
4. **Sanitize all user input**
5. **Add tests for new attack vectors**
6. **Document security assumptions**

### For Agent Developers

1. **Respect rate limits**
2. **Use idempotency keys for writes**
3. **Handle validation errors gracefully**
4. **Never expose raw error messages to end users**
5. **Implement exponential backoff**
6. **Cache non-sensitive results**

## Future Enhancements

### Planned Improvements

1. **Circuit Breaker Pattern**
   - Automatic throttling on downstream failures
   - Prevents cascade failures
   - Gradual recovery mechanisms

2. **Fine-Grained RBAC**
   - Role-based access control
   - Permission hierarchies
   - Dynamic policy updates

3. **Anomaly Detection**
   - ML-based behavior analysis
   - Automatic threat detection
   - Adaptive rate limiting

4. **Advanced Monitoring**
   - Real-time dashboards
   - Security event correlation
   - Automated incident response

## References

- [MCP Server Documentation](../mcp_server/README.md)
- [RAG Workflow Guide](./RAG_WORKFLOWS.md)
- [API Security Audit](../audit/api_code_quality.md)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

## Change Log

### 2024-10-12 - Enhanced Confinement Framework

- Added comprehensive input validation module
- Implemented read operation rate limiting
- Enhanced security event logging
- Extended RAG safety patterns (23 patterns total)
- Added 60+ security tests
- Created documentation

---

**Last Updated:** 2024-10-12  
**Maintainer:** Theo Engine Security Team
