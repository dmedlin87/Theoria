# OSSF Scorecard Workflow Permission Fixes

This document summarizes the changes made to comply with OSSF Scorecard security requirements.

## Changes Made

All GitHub workflow files have been updated to follow OSSF Scorecard restrictions as described in [scorecard-action workflow restrictions](https://github.com/ossf/scorecard-action#workflow-restrictions).

### Key Requirements Implemented

1. **Global permissions set to `read-all`** - All workflows now use restrictive global permissions
2. **No global `security-events: write`** - Moved to job-level where needed
3. **No global `id-token: write`** - Moved to job-level where needed
4. **Write permissions only at job level** - Specific permissions granted only to jobs that need them

### Files Updated

#### 1. `.github/workflows/deployment-sign.yml`
- **Before**: Global permissions included `packages: write`, `id-token: write`, `attestations: write`, `security-events: write`
- **After**: Global `permissions: read-all`, all write permissions moved to job level
- **Rationale**: This workflow needs write permissions for container signing and attestation

#### 2. `.github/workflows/security-codeql.yml`
- **Before**: Global `security-events: write`
- **After**: Global `permissions: read-all`, `security-events: write` moved to job level
- **Rationale**: CodeQL needs to upload SARIF results to security dashboard

#### 3. `.github/workflows/security-scorecard.yml`
- **Before**: Global `security-events: write` and `id-token: write`
- **After**: Global `permissions: read-all`, both permissions moved to job level
- **Rationale**: Scorecard needs to upload SARIF and sign attestations with OIDC

#### 4. `.github/workflows/security-zap.yml`
- **Before**: Global `security-events: write`
- **After**: Global `permissions: read-all`, `security-events: write` moved to job level
- **Rationale**: ZAP needs to upload vulnerability scan results

#### 5. `.github/workflows/rag-eval.yml`
- **Before**: No permissions block (defaulted to broad permissions)
- **After**: Global `permissions: read-all`
- **Rationale**: This workflow only needs read access

### Files Already Compliant

These workflows already had compliant permission structures:

- `.github/workflows/ci.yml` - Uses `contents: read` and `pull-requests: read`
- `.github/workflows/lighthouse.yml` - Uses `contents: read`
- `.github/workflows/secret-scanning.yml` - Uses `contents: read`

## Security Benefits

1. **Principle of Least Privilege**: Each job only gets the minimum permissions it needs
2. **Reduced Attack Surface**: Global write permissions eliminated
3. **OSSF Scorecard Compliance**: Improves security posture scoring
4. **Token Security**: Prevents unauthorized access if workflow is compromised

## Validation

After merging these changes:
1. Monitor workflow runs to ensure they continue to function correctly
2. Check OSSF Scorecard results for improved "Token-Permissions" score
3. Verify all security tools (CodeQL, Scorecard, ZAP) still upload results successfully

## References

- [OSSF Scorecard Action Workflow Restrictions](https://github.com/ossf/scorecard-action#workflow-restrictions)
- [GitHub Actions Permissions Documentation](https://docs.github.com/en/actions/security-guides/automatic-token-authentication#permissions-for-the-github_token)
- [Security Hardening for GitHub Actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)