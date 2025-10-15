# Lighthouse CI Baseline

This directory stores baseline Lighthouse scores for performance comparison in CI/CD.

## Purpose

Lighthouse CI compares current audit results against these baseline scores to:
- Detect performance regressions before they reach production
- Track improvements over time
- Enforce quality gates in pull requests

## Pages Tested

Baseline includes scores for **3 critical user journeys**:
- **/** - Homepage (first impression)
- **/verse/John.3.16** - Verse detail page (most common content)
- **/search** - Search page (interactive heavy)

Each page has independent performance, accessibility, best-practices, and SEO scores.

## Updating Baseline

### Option 1: Automated Script (Recommended)

```bash
# Start the dev or production server
cd theo/services/web
npm run build && npm run start

# In another terminal, run the baseline initializer
node scripts/lighthouse-init-baseline.mjs
```

The script will:
1. Verify server is running
2. Run Lighthouse audits on all 3 pages
3. Save results to `.lighthouseci/baseline/`
4. Validate the baseline is complete

### Option 2: Manual Update

```bash
# Run local Lighthouse audit
cd theo/services/web
npm run test:lighthouse:smoke

# Copy results to baseline
cp .lighthouseci/manifest.json ../../.lighthouseci/baseline/manifest.json
```

### When to Update Baseline

Only update baseline when:
- **Performance optimizations** - Should see improvements ()
- **Intentional features** - Slight regressions acceptable if justified and documented
- **Infrastructure changes** - After Next.js upgrades, new bundler settings, etc.
- **Never to pass CI** - Fix the performance issue instead!

**After updating:** Commit the new `manifest.json` and include performance delta in PR description.

## Files

- `manifest.json` - **Summary scores** for all 3 audited pages (required)
- `lhr-*.html` - Full Lighthouse reports (optional, for detailed review)
- `lhr-*.json` - Raw audit data (optional, for programmatic analysis)

## CI Integration

The GitHub Actions Lighthouse workflow:
1. Runs audits on current code (all 3 pages)
2. Compares results with this baseline
3. Flags regressions: >5pt performance drop, >2pt other categories
4. Shows delta in PR summary with visual indicators (/)
5. Fails if assertions or budgets exceeded

## Performance Budgets

In addition to score comparisons, budgets enforce:
- **JS Bundle:** ≤ 300 KB
- **CSS:** ≤ 75 KB  
- **Images:** ≤ 200 KB
- **Total Page:** ≤ 800 KB
- **Time to Interactive:** ≤ 3500 ms
- **First Contentful Paint:** ≤ 1500 ms

Budget violations fail CI even if scores are acceptable.

## Debugging Score Changes

If scores drop unexpectedly:

1. **Download artifacts** from failed CI run (`lighthouse-results-localhost-XXX`)
2. **Open HTML reports** in browser for detailed breakdown
3. **Review "Opportunities"** section for optimization suggestions
4. **Check bundle analyzer**: `cd theo/services/web && ANALYZE=true npm run build`
5. **Compare network waterfalls** between baseline and current reports

## References

- **Initialization Script:** `scripts/lighthouse-init-baseline.mjs`
- **Comparison Script:** `scripts/compare-lighthouse-baseline.mjs`  
- **Workflow:** `.github/workflows/lighthouse.yml`
- **Config:** `lighthouserc.json`
- **Full Docs:** `docs/LIGHTHOUSE_ENHANCEMENTS.md`
