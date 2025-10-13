# CI/CD Pipeline Action Items

**Generated:** October 13, 2025  
**Source:** `cicd_pipeline_review.md`

This document provides actionable tasks derived from the CI/CD pipeline review, organized by priority and effort.

---

## Priority 1: Critical (Implement This Week)

### 1. Standardize TruffleHog Configuration
**Impact:** Security consistency  
**Effort:** 15 minutes  
**Risk:** Low

**Current Issue:**
- `ci.yml` uses `--only-verified --fail`
- `secret-scanning.yml` uses default (all findings, no fail)

**Action:**
```yaml
# Update .github/workflows/secret-scanning.yml line 28
extra_args: "--only-verified --fail --json --results-file trufflehog-findings.json"
```

**Verification:**
```bash
# After change, trigger both workflows and ensure behavior matches
gh workflow run secret-scanning.yml
```

---

### 2. Add Missing Job Timeouts
**Impact:** Prevents hung workflows consuming minutes  
**Effort:** 10 minutes  
**Risk:** None

**Files to Update:**
- `.github/workflows/ci.yml` - test job (line 13)
- `.github/workflows/ci.yml` - web_lighthouse job (line 276)
- `.github/workflows/security-codeql.yml` - analyze job (line 16)
- `.github/workflows/security-scorecard.yml` - analysis job (line 16)

**Template:**
```yaml
jobs:
  test:
    timeout-minutes: 45  # Add this line
    runs-on: ubuntu-latest
    
  web_accessibility:
    timeout-minutes: 30  # Add this line
    
  web_visual_regression:
    timeout-minutes: 30  # Add this line
    
  web_lighthouse:
    timeout-minutes: 20  # Add this line
```

**Verification:**
```bash
# Check all workflows have timeouts
grep -r "timeout-minutes" .github/workflows/
```

---

### 3. Add Container Vulnerability Scanning
**Impact:** Prevents shipping vulnerable images  
**Effort:** 30 minutes  
**Risk:** Medium (may detect existing vulnerabilities)

**Location:** `.github/workflows/deployment-sign.yml` after line 67 (after SBOM generation)

**Implementation:**
```yaml
- name: Scan image for vulnerabilities
  id: scan
  uses: aquasecurity/trivy-action@0.28.0
  with:
    image-ref: ${{ steps.meta.outputs.image }}@${{ steps.build.outputs.digest }}
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'
    exit-code: '1'

- name: Upload Trivy SARIF to Security tab
  if: always()
  uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: 'trivy-results.sarif'
    category: container-image-scan

- name: Upload Trivy results artifact
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: trivy-scan-results
    path: trivy-results.sarif
```

**Note:** This WILL fail if critical/high vulnerabilities exist. Plan remediation time.

---

## Priority 2: High (Implement This Month)

### 4. Create Composite Action for Python Setup
**Impact:** Reduces duplication, easier maintenance  
**Effort:** 1 hour  
**Risk:** Low

**Create:** `.github/actions/setup-python-theo/action.yml`

```yaml
name: Setup Python Environment for TheoEngine
description: Sets up Python with caching and installs dependencies

inputs:
  python-version:
    description: Python version to use
    required: false
    default: '3.11'
  install-dev:
    description: Install dev dependencies
    required: false
    default: 'true'

runs:
  using: composite
  steps:
    - name: Set up Python
      uses: actions/setup-python@v6
      with:
        python-version: ${{ inputs.python-version }}
        cache: 'pip'
        cache-dependency-path: |
          requirements.txt
          requirements-dev.txt

    - name: Install Python dependencies
      shell: bash
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        if [ "${{ inputs.install-dev }}" = "true" ]; then
          pip install -r requirements-dev.txt
        fi

    - name: Set environment variables
      shell: bash
      run: |
        echo "PYTHONPATH=${{ github.workspace }}" >> $GITHUB_ENV
        echo "SETTINGS_SECRET_KEY=geo-ci-secret" >> $GITHUB_ENV
        echo "FIXTURES_ROOT=${{ github.workspace }}/fixtures" >> $GITHUB_ENV
```

**Update workflows to use:**
```yaml
# Replace setup-python steps in ci.yml with:
- uses: ./.github/actions/setup-python-theo
```

**Files to update:**
- `.github/workflows/ci.yml` (4 locations)
- `.github/workflows/rag-eval.yml` (1 location)

---

### 5. Add Playwright Browser Caching
**Impact:** Saves ~5 minutes per workflow run  
**Effort:** 30 minutes  
**Risk:** Low (cache invalidation might need tuning)

**Location:** `.github/workflows/ci.yml` before line 49

**Implementation:**
```yaml
- name: Get Playwright version
  id: playwright-version
  working-directory: theo/services/web
  run: |
    VERSION=$(node -p "require('./package-lock.json').packages['node_modules/@playwright/test'].version")
    echo "version=$VERSION" >> $GITHUB_OUTPUT

- name: Cache Playwright browsers
  uses: actions/cache@v4
  id: playwright-cache
  with:
    path: ~/.cache/ms-playwright
    key: playwright-${{ runner.os }}-${{ steps.playwright-version.outputs.version }}

- name: Install Playwright browsers
  if: steps.playwright-cache.outputs.cache-hit != 'true'
  working-directory: theo/services/web
  run: npx playwright install --with-deps
```

**Apply to:**
- `test` job (line 49)
- `web_accessibility` job (line 174)
- `web_visual_regression` job (line 251)

---

### 6. Configure Dependabot
**Impact:** Automated security updates  
**Effort:** 20 minutes  
**Risk:** Creates PR noise (can configure labels/reviewers)

**Create:** `.github/dependabot.yml`

```yaml
version: 2
updates:
  # GitHub Actions dependencies
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "06:00"
    labels:
      - "dependencies"
      - "github-actions"
      - "security"
    reviewers:
      - "dmedlin87"  # Replace with your team
    commit-message:
      prefix: "chore(deps)"

  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "06:00"
    labels:
      - "dependencies"
      - "python"
    groups:
      dev-dependencies:
        patterns:
          - "pytest*"
          - "ruff*"
          - "mypy*"
    commit-message:
      prefix: "chore(deps)"

  # Node.js dependencies
  - package-ecosystem: "npm"
    directory: "/theo/services/web"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "06:00"
    labels:
      - "dependencies"
      - "nodejs"
    groups:
      dev-dependencies:
        patterns:
          - "@types/*"
          - "eslint*"
          - "@playwright/*"
    commit-message:
      prefix: "chore(deps)"
```

**Post-implementation:**
- Monitor first week of PRs
- Adjust grouping if too many PRs
- Consider auto-merge for patch updates (with strong test coverage)

---

### 7. Create Deployment Workflow
**Impact:** Complete CI/CD cycle  
**Effort:** 2-4 hours  
**Risk:** Medium (requires staging/production infrastructure)

**Create:** `.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  workflow_run:
    workflows: ["Release Containers"]
    types: [completed]
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy'
        required: true
        type: choice
        options:
          - staging
          - production
      image_tag:
        description: 'Image tag to deploy'
        required: true

permissions:
  contents: read
  deployments: write

jobs:
  verify-image:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}
    outputs:
      image_digest: ${{ steps.verify.outputs.digest }}
    steps:
      - name: Install Cosign
        uses: sigstore/cosign-installer@v3.10.0

      - name: Verify image signature
        id: verify
        env:
          IMAGE_TAG: ${{ github.event.inputs.image_tag || github.sha }}
        run: |
          IMAGE="ghcr.io/${{ github.repository_owner }}/theoria-api:${IMAGE_TAG}"
          EXPECTED_IDENTITY="https://github.com/${{ github.repository }}/.github/workflows/deployment-sign.yml@refs/heads/main"
          
          cosign verify \
            --certificate-identity "${EXPECTED_IDENTITY}" \
            --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
            "${IMAGE}"
          
          DIGEST=$(docker manifest inspect "${IMAGE}" | jq -r '.config.digest')
          echo "digest=${DIGEST}" >> $GITHUB_OUTPUT

  deploy-staging:
    needs: verify-image
    runs-on: ubuntu-latest
    environment: staging
    if: ${{ github.event.inputs.environment == 'staging' || github.event_name == 'workflow_run' }}
    steps:
      - name: Deploy to staging
        run: |
          # Add your deployment commands here
          # Examples:
          # - kubectl set image deployment/theoria-api ...
          # - docker stack deploy ...
          # - terraform apply ...
          echo "Deploying ${{ needs.verify-image.outputs.image_digest }} to staging"

      - name: Wait for deployment
        run: |
          # Add health check polling
          echo "Waiting for staging to be healthy..."

  smoke-test-staging:
    needs: deploy-staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Run smoke tests
        env:
          API_BASE_URL: ${{ secrets.STAGING_API_BASE_URL }}
        run: |
          # Add smoke test commands
          curl -f "${API_BASE_URL}/health" || exit 1

  deploy-production:
    needs: [verify-image, smoke-test-staging]
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    if: ${{ github.event.inputs.environment == 'production' }}
    steps:
      - name: Deploy to production
        run: |
          # Add your production deployment commands
          echo "Deploying ${{ needs.verify-image.outputs.image_digest }} to production"

      - name: Create deployment record
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.repos.createDeployment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: context.sha,
              environment: 'production',
              auto_merge: false
            });
```

**Prerequisites:**
- Configure GitHub environments (Settings → Environments)
  - `staging` (no protection)
  - `production` (required reviewers)
- Set deployment secrets
- Configure deployment targets (K8s, Docker Swarm, etc.)

---

## Priority 3: Medium (Implement This Quarter)

### 8. Add Performance Regression Gates
**Impact:** Prevent performance regressions  
**Effort:** 2 hours  
**Risk:** Low (may need threshold tuning)

**Create:** `scripts/perf/check_lighthouse_budget.js`

```javascript
const fs = require('fs');

const BUDGETS = {
  performance: 90,
  accessibility: 95,
  'best-practices': 90,
  seo: 90,
  pwa: 60
};

const REGRESSION_THRESHOLD = 5; // points

const manifest = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const baseline = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));

let failures = [];

for (const [metric, minScore] of Object.entries(BUDGETS)) {
  const current = manifest[0]?.summary?.[metric] || 0;
  const previous = baseline[0]?.summary?.[metric] || 0;
  const delta = current - previous;

  if (current < minScore) {
    failures.push(`${metric}: ${current} < budget ${minScore}`);
  }
  
  if (delta < -REGRESSION_THRESHOLD) {
    failures.push(`${metric}: regressed ${Math.abs(delta)} points`);
  }
}

if (failures.length > 0) {
  console.error('❌ Performance budget violations:');
  failures.forEach(f => console.error(`  - ${f}`));
  process.exit(1);
} else {
  console.log('✅ All performance budgets met');
}
```

**Add to `.github/workflows/lighthouse.yml` after line 147:**

```yaml
- name: Enforce performance budgets
  run: |
    node ../../../scripts/perf/check_lighthouse_budget.js \
      .lighthouseci/current/manifest.json \
      ../../../.lighthouseci/baseline/manifest.json
```

---

### 9. Document Security Architecture
**Impact:** Team understanding, compliance  
**Effort:** 1 hour  
**Risk:** None

**Create:** `.github/SECURITY_ARCHITECTURE.md`

```markdown
# Security Architecture

## Defense Layers

### 1. Secret Scanning (TruffleHog)
- **Trigger:** Every push, PR, weekly
- **Scope:** All repository history
- **Action:** Blocks merge on verified secrets
- **Config:** `--only-verified --fail`

### 2. Static Analysis (CodeQL)
- **Languages:** Python, JavaScript
- **Schedule:** Weekly Monday 5 AM UTC
- **Integration:** GitHub Security tab (SARIF)

### 3. Dynamic Analysis (OWASP ZAP)
- **Target:** Staging API (`STAGING_API_BASE_URL`)
- **Schedule:** Weekly Monday 3:30 AM UTC
- **Severity Gate:** High severity blocks merge
- **Script:** `scripts/security/zap_severity_gate.py`

### 4. Supply Chain (OpenSSF Scorecard)
- **Schedule:** Weekly Monday 6 AM UTC
- **Visibility:** Public results published
- **Integration:** GitHub Security tab

### 5. Container Security
- **Image Signing:** Sigstore/Cosign (keyless)
- **Attestation:** Build provenance with SBOM
- **Verification:** In-workflow signature check
- **Vulnerability Scanning:** Trivy (TODO)

### 6. Dependency Management
- **SBOMs:** CycloneDX for Python + Node.js
- **Updates:** Dependabot (TODO)
- **Audit:** npm audit in CI

## Incident Response

### Compromised Secret
1. Revoke immediately in provider (AWS, etc.)
2. Check TruffleHog artifacts for exposure timeline
3. Rotate all related credentials
4. Review ZAP/CodeQL for related vulnerabilities

### Container Vulnerability
1. Check Trivy SARIF in Security tab
2. Identify affected image tags
3. Apply patch and rebuild
4. Verify new image signature
5. Redeploy with patched image

### Failed Security Scan
- **ZAP high severity:** Review `zap-baseline-report.html` artifact
- **CodeQL alert:** Check Security tab → Code scanning
- **TruffleHog:** Review `trufflehog-findings.json`

## Compliance

- **SBOM:** Available in release artifacts
- **Provenance:** Sigstore transparency log
- **Audit Trail:** GitHub Actions logs (90 days)
- **Signatures:** Cosign public registry

## Contact
- Security Lead: [Name]
- Escalation: security@theoria.dev
```

---

### 10. Add RAG Metric Regression Detection
**Impact:** Catch AI quality regressions  
**Effort:** 2 hours  
**Risk:** Low

**Create:** `scripts/perf/compare_rag_metrics.py`

```python
#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

THRESHOLDS = {
    "answer_relevancy": 0.05,  # 5% tolerance
    "faithfulness": 0.05,
    "context_precision": 0.05,
}

def load_metrics(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)

def compare_metrics(current: dict, baseline: dict, threshold: float) -> list[str]:
    failures = []
    
    for metric, max_delta in THRESHOLDS.items():
        curr_val = current.get(metric, 0)
        base_val = baseline.get(metric, 0)
        delta = curr_val - base_val
        
        if delta < -max_delta:
            failures.append(
                f"{metric}: {curr_val:.3f} vs baseline {base_val:.3f} "
                f"(regression: {abs(delta):.3f})"
            )
    
    return failures

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("current", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--fail-on-regression", action="store_true")
    
    args = parser.parse_args()
    
    current = load_metrics(args.current)
    baseline = load_metrics(args.baseline)
    
    failures = compare_metrics(current, baseline, 0.05)
    
    if failures:
        print("❌ RAG metric regressions detected:")
        for failure in failures:
            print(f"  - {failure}")
        
        if args.fail_on_regression:
            sys.exit(1)
    else:
        print("✅ No RAG metric regressions")

if __name__ == "__main__":
    main()
```

**Add to `.github/workflows/rag-eval.yml`:**

```yaml
- name: Check for regressions
  run: |
    python scripts/perf/compare_rag_metrics.py \
      perf_metrics/current.json \
      data/eval/baseline.json \
      --fail-on-regression
```

---

## Implementation Roadmap

### Week 1 (Critical)
- [ ] Standardize TruffleHog config (15 min)
- [ ] Add job timeouts (10 min)
- [ ] Add container scanning (30 min)

### Week 2-4 (High Priority)
- [ ] Create Python composite action (1 hour)
- [ ] Add Playwright caching (30 min)
- [ ] Configure Dependabot (20 min)
- [ ] Create deployment workflow (2-4 hours)

### Month 2-3 (Medium Priority)
- [ ] Add performance budgets (2 hours)
- [ ] Document security architecture (1 hour)
- [ ] Add RAG regression detection (2 hours)

---

## Validation Checklist

After implementing each action item:

- [ ] Workflow syntax validated locally: `gh workflow view <workflow>.yml`
- [ ] Changes tested in feature branch
- [ ] All jobs complete successfully
- [ ] Artifacts uploaded correctly
- [ ] Documentation updated
- [ ] Team notified of changes

---

**Last Updated:** 2025-10-13  
**Next Review:** 2025-11-13 (monthly cadence)
