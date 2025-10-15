# Lighthouse CI Enhancements

**Date:** 2025-01-14  
**Status:** Implemented

## Overview

Enhanced Lighthouse CI with multi-page testing, performance budgets, better error handling, and improved reporting to catch performance regressions more effectively.

## New Features

### 1. **Multi-Page Testing** 🎯

Previously tested only the homepage. Now audits **3 critical user journeys**:

- **Homepage** (`/`) - First impression, core metrics
- **Verse Detail** (`/verse/John.3.16`) - Most common content page
- **Search** (`/search`) - Interactive heavy page

Each page is tested independently with separate scores and budgets.

### 2. **Performance Budgets** 💰

Added resource and timing budgets to prevent bundle bloat:

| Budget Type | Resource | Limit | Purpose |
|------------|----------|-------|---------|
| **Size** | JavaScript | 300 KB | Prevent bundle bloat |
| **Size** | Stylesheets | 75 KB | Keep CSS minimal |
| **Size** | Images | 200 KB | Optimize assets |
| **Size** | Fonts | 100 KB | Limit font files |
| **Size** | Total | 800 KB | Overall page weight |
| **Count** | Scripts | 15 files | Limit HTTP requests |
| **Count** | Stylesheets | 5 files | Reduce render blocking |
| **Count** | Third-party | 10 resources | Control external deps |
| **Timing** | Time to Interactive | 3500 ms | User responsiveness |
| **Timing** | First Contentful Paint | 1500 ms | Perceived speed |

**Lighthouse will fail** if any budget is exceeded, forcing you to optimize before merge.

### 3. **Desktop Testing with Throttling** 🖥️

- Explicit **desktop preset** (1350x940 viewport)
- Faster network throttling (10 Mbps vs simulated 4G)
- Lower CPU throttling (1x vs 4x) to match CI runners
- Still realistic enough to catch performance issues

### 4. **Enhanced Comparison Reporting** 📊

Improved baseline comparison with visual indicators:

```
## Lighthouse Performance Comparison

### /

- Performance: 🟢 **95.0** (baseline 90.0, +5.0)
- Accessibility: 97.0 (no change)
- Best Practices: 98.0 (baseline 97.5, +0.5)
- SEO: 90.0 (no change)

### /verse/John.3.16

- Performance: 🔴 **85.0** (baseline 92.0, -7.0)
- Accessibility: 96.0 (baseline 97.0, -1.0)
- Best Practices: 95.0 (no change)
- SEO: 91.0 (no change)

⚠️ **Performance regressions detected** - Review the changes above before merging.
```

**Regression thresholds:**
- Performance: > 5 points drop = 🔴 flag
- Other categories: > 2 points drop = 🔴 flag
- Improvements: > threshold = 🟢 highlight

### 5. **Exponential Backoff Server Wait** ⏱️

Replaced fixed 2-second retry intervals with smart backoff:

- 1st attempt: immediate
- 2nd attempt: 2s wait
- 3rd attempt: 4s wait
- 4th+ attempts: 5s wait (capped)
- Total timeout: 60 seconds
- Better logging: `[3/20] Server not ready, waiting 4s...`

Faster successful starts (typically 5-10s) while maintaining reliability.

### 6. **Better Artifact Management** 📦

- Artifact names include environment: `lighthouse-results-localhost-123`
- 30-day retention (was indefinite)
- Easier to find specific runs when debugging
- Separate localhost vs staging results

## Configuration Changes

### `lighthouserc.json`

```json
{
  "ci": {
    "collect": {
      "url": [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3000/verse/John.3.16",
        "http://127.0.0.1:3000/search"
      ],
      "numberOfRuns": 1,
      "settings": {
        "preset": "desktop",
        "chromeFlags": "--headless=new --no-sandbox --disable-dev-shm-usage",
        "throttling": {
          "rttMs": 40,
          "throughputKbps": 10240,
          "cpuSlowdownMultiplier": 1
        }
      }
    },
    "budgets": [ /* resource budgets */ ]
  }
}
```

**Key points:**
- URLs are templates - workflow injects actual origin (localhost/staging)
- Desktop preset for CI realism
- Budgets apply to all pages via `"path": "/*"`

### `.github/workflows/lighthouse.yml`

- Dynamic URL injection based on target environment
- Improved server readiness check with backoff
- Better artifact naming with run number
- Enhanced comparison script integration

## Usage

### Running Locally

Test all three pages with budgets:

```bash
cd theo/services/web
npm run build
npm run start

# In another terminal:
npm run test:lighthouse:smoke
```

### Updating Baseline

After intentional performance changes, update the baseline:

```bash
# Ensure server is running
cd theo/services/web && npm run start

# In another terminal:
node scripts/lighthouse-init-baseline.mjs
```

This updates `.lighthouseci/baseline/manifest.json` with new scores.

**When to update baseline:**
- ✅ After performance optimizations (should see improvements)
- ✅ After intentional feature additions (slight regressions acceptable if justified)
- ❌ Never update just to pass CI - fix the performance issue!

### Manual Workflow Dispatch

Test against staging:

1. Go to GitHub Actions → Lighthouse CI
2. Click "Run workflow"
3. Select `target: staging`
4. Review results in artifacts

## Monitoring

### Budget Violations

Budget failures appear in Lighthouse CI output:

```
✗ categories:performance assertion failed
✗ resource-summary.script.size exceeded budget (350 KB > 300 KB)
```

**Action:** Review bundle analyzer output, code-split, or lazy-load:

```bash
cd theo/services/web
ANALYZE=true npm run build
```

### Performance Regressions

Check the comparison in GitHub Actions step summary for 🔴 indicators.

**Debugging:**
1. Download `lighthouse-results-localhost-XXX` artifact
2. Open `.lighthouseci/lhr-*.html` reports in browser
3. Review "Opportunities" and "Diagnostics" sections
4. Compare network waterfall between baseline and current

### Trend Analysis

Track scores over time:

```bash
# Extract performance scores from recent runs
gh run list --workflow=lighthouse.yml --json conclusion,createdAt | \
  jq '.[] | select(.conclusion=="success")'
```

Consider adding Lighthouse CI Server for persistent trend tracking if needed.

## Troubleshooting

### "Server not ready after 60s"

- Check `server.log` in artifacts for Next.js startup errors
- Verify build succeeded (look for `.next` directory artifacts)
- Ensure no port conflicts (should be isolated in CI)

### Budget Failures After Dependency Update

Common after adding/upgrading npm packages:

1. Check bundle analyzer: `ANALYZE=true npm run build`
2. Look for new large dependencies
3. Consider: tree-shaking, dynamic imports, or lighter alternatives
4. Update budgets only if increase is justified and documented

### Staging Unreachable

Workflow skips LHCI if staging is down (by design):

```
Note skip (staging unreachable)
Skipping LHCI; https://staging.theoengine.com unreachable.
```

Staging tests are optional - localhost tests always run.

## Future Enhancements

Potential additions if needed:

- [ ] Mobile preset testing (separate workflow/job)
- [ ] Custom Lighthouse plugins (e.g., PWA checks)
- [ ] Performance trend dashboard
- [ ] Lighthouse CI Server for historical data
- [ ] Auto-comment PR with score deltas
- [ ] Critical path analysis

## References

- **Config:** `lighthouserc.json`
- **Workflow:** `.github/workflows/lighthouse.yml`
- **Comparison Script:** `scripts/compare-lighthouse-baseline.mjs`
- **Init Script:** `scripts/lighthouse-init-baseline.mjs`
- **Lighthouse CI Docs:** https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/getting-started.md
- **Budget Docs:** https://web.dev/use-lighthouse-for-performance-budgets/
