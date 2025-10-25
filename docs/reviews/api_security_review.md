---
title: "API Security Review"
date: 2025-10-24
status: draft
reviewed_by: Cascade AI
---

# API Security Review – October 2025

## Summary

We audited the Theo Engine HTTP and GraphQL APIs for security and robustness issues. Most routers inherit the shared authentication guard, but several mounts and endpoints circumvent it or expose sensitive metadata. Addressing the items below will align the service with the documented security posture.

## Findings

### 1. GraphQL router bypasses authentication
- **Location:** `theo/services/api/app/infra/router_registry.py` registers `graphql_router` without enforcing the shared `require_principal` dependency. See @theo/services/api/app/infra/router_registry.py#28-95 and @theo/services/api/app/main.py#291-347.
- **Impact:** `/graphql` appears publicly accessible, allowing unauthenticated queries into the schema.
- **Recommendation:** Wrap the router with the security dependency (e.g., include via an authenticated prefix or attach `dependencies=[Depends(require_principal)]`). Add regression tests for unauthenticated access.

### 2. Dashboard summary exposed without auth
- **Location:** @theo/services/api/app/routes/dashboard.py#222-303 lacks `Depends(require_principal)`.
- **Impact:** Unauthenticated callers can enumerate global counts and recent activity.
- **Recommendation:** Require authentication and scope data by principal where possible.

### 3. Mixed websocket authentication coverage
- **Location:** Websocket route uses custom guard, but polling endpoint uses default dependency (@theo/services/api/app/routes/realtime.py#105-138).
- **Impact:** Inconsistent enforcement could let unauthenticated clients poll notebook state.
- **Recommendation:** Ensure both websocket and REST polling paths share the same auth mechanism and consider rate limiting/broadcast controls.

### 4. Ingestion payload validation gaps
- **Location:** Ingestion routes accept arbitrary `frontmatter` and pass directly to persistence (@theo/services/api/app/routes/ingest.py#214-432).
- **Impact:** Large or malicious payloads could stress the service or introduce unsafe metadata.
- **Recommendation:** Enforce schema validation, size limits, and threat modeling for stored metadata.

### 5. Tenant-scoped metrics missing
- **Location:** Dashboard metrics query entire tables without user filters (@theo/services/api/app/routes/dashboard.py#232-292).
- **Impact:** Multi-tenant deployments may leak aggregate counts across users.
- **Recommendation:** Scope metrics to the authenticated user or document why global totals are acceptable.

### 6. Duplicate export router registration
- **Location:** `export.router` is included twice, once at `/export` and once via `api_router` (@theo/services/api/app/infra/router_registry.py#32-34 and @theo/services/api/app/routes/export.py#50-661).
- **Impact:** Confusing surface area; the unprefixed mount may bypass security middleware or documentation expectations.
- **Recommendation:** Consolidate on a single mount path and verify dependency injection matches security requirements.

### 7. Experimental header parsing without limits
- **Location:** Search endpoint aggregates tokens from headers/query without bounds (@theo/services/api/app/routes/search.py#103-120).
- **Impact:** Attackers could send very large headers to consume memory.
- **Recommendation:** Set maximum length/count for `experiment` tokens and respond with 400 on overflow.

### 8. Feature discovery leakage
- **Location:** Feature flags exposed anonymously via @theo/services/api/app/routes/features.py#12-45.
- **Impact:** Reveals deployment capabilities to unauthenticated parties.
- **Recommendation:** Require authentication or document acceptable exposure.

### 9. Anonymous startup mode warning only
- **Location:** Authentication guard logs warning yet continues when `THEO_ALLOW_INSECURE_STARTUP=1` (@theo/services/api/app/main.py#359-385).
- **Impact:** Risk if non-dev deployments enable the flag inadvertently.
- **Recommendation:** Add defense-in-depth checks (environment allowlist, metrics) to prevent accidental unsecured deployments.

## Recommendations Summary

1. Protect `/graphql` with `require_principal` and add tests.
2. Apply authentication to dashboard and feature routes; ensure tenant scoping.
3. Standardize notebook realtime auth and add throttling.
4. Harden ingestion input validation and size limits.
5. Audit multi-tenant data exposure and document acceptable global metrics.
6. Resolve duplicate export router mounts.
7. Bound experiment header parsing.
8. Decide on public feature exposure or guard it.
9. Strengthen safeguards around insecure startup mode.

## Next Steps

1. Create tickets for each finding with priority labels (P0 for auth bypasses, P1 for validation/scoping).
2. Implement fixes with targeted regression tests (auth access, tenant scoping, header limits).
3. Update API documentation and changelog once mitigations land.
4. Schedule follow-up review to verify remediation and monitor relevant telemetry.
