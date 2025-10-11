# UI/UX Action Plan - TheoEngine

**Sprint Planning Guide | Priority-Based Roadmap**

---

## Overview

Based on the comprehensive UI/UX review, this document provides an actionable, sprint-by-sprint plan to address identified issues. All work items are prioritized by impact and effort.

---

## Sprint 1-2: Critical Path (2 weeks)

**Goal:** Address highest-impact issues with quick wins

### Week 1: Visual & Accessibility Quick Fixes

#### 1. Replace Emoji Icons with Lucide React (1 day)
**Impact:** High | **Effort:** Low | **Priority:** P0

```bash
npm install lucide-react
```

**Files to update:**
- `app/chat/ChatWorkspace.tsx` (🔍 📖 📤 → Search, Book, Upload)
- `app/chat/ChatWorkspace.tsx` (✅ 🌐 📝 → Check, Globe, FileText)
- All other emoji usage across app

**PR Checklist:**
- [ ] Replace all emoji icons (search codebase for emoji regex)
- [ ] Update ARIA labels to match icon semantics
- [ ] Ensure consistent icon sizing (20px default)
- [ ] Add icon color theming

#### 2. Hide Disabled Command Palette (30 minutes)
**Impact:** Medium | **Effort:** Low | **Priority:** P0

```tsx
// app/components/AppShell.tsx
{/* TODO: Implement command palette - hiding until ready */}
{false && (
  <button className="app-shell-v2__command-search" ...>
)}
```

**Alternative:** Show "Coming soon" only on hover, not prominently displayed.

#### 3. Standardize Form Error Display (1 day)
**Impact:** Medium | **Effort:** Low | **Priority:** P1

Create `FormError` component:
```tsx
// app/components/FormError.tsx
export function FormError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <div className="form-error" role="alert">
      {message}
    </div>
  );
}
```

Apply to all forms with validation.

### Week 2: Toast Integration & Loading States

#### 4. Integrate Toast Provider Globally (1 day)
**Impact:** High | **Effort:** Low | **Priority:** P0

```tsx
// app/layout.tsx
import { ToastProvider } from "./components/Toast";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          <ModeProvider>
            {/* existing content */}
          </ModeProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
```

#### 5. Migrate alert() to Toast (2 days)
**Impact:** Medium | **Effort:** Medium | **Priority:** P1

**Files to update:**
- `app/upload/page.tsx` (success/error feedback)
- `app/copilot/page.tsx` (workflow completion)
- `app/search/components/SearchPageClient.tsx` (saved searches)

**Pattern:**
```tsx
// Before
alert("Search saved!");

// After
const { addToast } = useToast();
addToast({ type: "success", message: "Search saved!" });
```

#### 6. Add Loading Skeletons to Top 3 Pages (2 days)
**Impact:** High | **Effort:** Medium | **Priority:** P1

**Target pages:**
1. `/search` - Add `<SkeletonCard />` while results load
2. `/verse/[osis]` - Add skeleton for mentions list
3. `/copilot` - Add skeleton for workflow results

```tsx
{isLoading ? (
  <SkeletonList count={5} />
) : (
  results.map(item => <ResultCard {...item} />)
)}
```

---

## Sprint 3-4: Component Refactoring (2 weeks)

**Goal:** Reduce technical debt by refactoring largest components

### Week 3: SearchPageClient Refactoring

#### 7. Refactor SearchPageClient.tsx (1785 → ~400 lines) (5 days)
**Impact:** Very High | **Effort:** High | **Priority:** P0

**Components already exist!** Just integrate:

```tsx
// app/search/components/SearchPageClient.tsx
import { useSearchFilters } from '../hooks/useSearchFilters';
import { SearchFilters } from './SearchFilters';
import { SearchResults } from './SearchResults';
import { FilterChips } from './FilterChips';

export default function SearchPageClient({ initialFilters, ... }) {
  const {
    filters,
    setters,
    resetFilters,
    toggleFacet
  } = useSearchFilters(initialFilters);

  return (
    <div className="search-page">
      <SearchFilters
        {...filters}
        {...setters}
        onReset={resetFilters}
      />
      <FilterChips 
        filters={filters}
        onRemoveFilter={handleRemoveFilter}
      />
      <SearchResults
        groups={results}
        queryTokens={queryTokens}
        onPassageClick={handlePassageClick}
      />
    </div>
  );
}
```

**Acceptance criteria:**
- [ ] File reduced to < 500 lines
- [ ] All filters functional
- [ ] All existing features preserved
- [ ] E2E tests still pass
- [ ] No inline styles remain

### Week 4: Upload & Copilot Refactoring

#### 8. Refactor UploadPage.tsx (846 → ~250 lines) (2 days)
**Impact:** High | **Effort:** Medium | **Priority:** P1

Use existing components:
- `FileUploadForm` ✅
- `UrlIngestForm` ✅
- `JobsTable` ✅

#### 9. Refactor CopilotPage.tsx (837 → ~350 lines) (3 days)
**Impact:** High | **Effort:** High | **Priority:** P1

Use existing components:
- `VerseWorkflowForm` ✅
- `WorkflowTabs` ✅
- `WorkflowFormFields` ✅

---

## Sprint 5-6: Inline Style Elimination (2 weeks)

**Goal:** Remove all 642 inline styles

### Week 5: Top Offenders

#### 10. Eliminate Inline Styles - Phase 1 (5 days)
**Impact:** High | **Effort:** High | **Priority:** P1

**Target files (288 inline styles):**
1. `SearchPageClient.tsx`: 84 → 0 ✓ (already done in Sprint 3)
2. `upload/page.tsx`: 63 → 0 ✓ (already done in Sprint 4)
3. `TextualVariantsPanel.tsx`: 56 inline styles
4. `DocumentClient.tsx`: 45 inline styles
5. `notebooks/[id]/page.tsx`: 36 inline styles

**Pattern:**
```tsx
// Before
<div style={{ display: "flex", gap: "1rem", padding: "1rem" }}>

// After
<div className="stack-md p-2">
```

**Automation tool:**
```bash
# Find all inline styles
grep -r "style={{" app/ --include="*.tsx" | wc -l

# Progress tracker
# Week 1: 642 → 450
# Week 2: 450 → 250
# Week 3: 250 → 100
# Week 4: 100 → 0
```

### Week 6: Research Panels & Remaining Files

#### 11. Eliminate Inline Styles - Phase 2 (5 days)
**Impact:** Medium | **Effort:** Medium | **Priority:** P1

**Target files (354 inline styles):**
- `GeoPanel.tsx`: 28
- `CommentariesPanel.tsx`: 22
- `WorkflowFormFields.tsx`: 22
- `CitationList.tsx`: 24
- `ContradictionsPanelClient.tsx`: 24
- All remaining files: 234

---

## Sprint 7-8: Accessibility & Testing (2 weeks)

**Goal:** Achieve WCAG AA compliance and 80% test coverage

### Week 7: Accessibility Improvements

#### 12. Fix Heading Hierarchy (1 day)
**Impact:** Medium | **Effort:** Low | **Priority:** P2

Ensure logical heading order (h1 → h2 → h3, no skips).

**Files to audit:**
- All page.tsx files
- Main layout components

#### 13. Add ARIA Live Regions (1 day)
**Impact:** Medium | **Effort:** Low | **Priority:** P2

```tsx
// app/components/Toast.tsx
<div
  className="toast-container"
  aria-live="polite"
  aria-atomic="true"
>
  {toasts.map(toast => ...)}
</div>
```

#### 14. Implement Focus Trap for Modals (2 days)
**Impact:** Medium | **Effort:** Medium | **Priority:** P2

If/when modals are added, use `focus-trap-react`:
```tsx
import FocusTrap from 'focus-trap-react';

<FocusTrap>
  <div className="modal" role="dialog">
    {/* content */}
  </div>
</FocusTrap>
```

#### 15. Add Axe-Core to E2E Tests (1 day)
**Impact:** High | **Effort:** Low | **Priority:** P1

```bash
npm install -D @axe-core/playwright
```

```typescript
// tests/e2e/accessibility.spec.ts
import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

test('search page accessibility', async ({ page }) => {
  await page.goto('/search');
  await injectAxe(page);
  await checkA11y(page, undefined, {
    detailedReport: true,
    detailedReportOptions: { html: true }
  });
});
```

### Week 8: Component Testing

#### 16. Add Unit Tests for Shared Components (3 days)
**Impact:** High | **Effort:** Medium | **Priority:** P1

**Target coverage: 80%**

```tsx
// tests/components/Toast.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { ToastProvider, useToast } from '@/app/components/Toast';

describe('Toast', () => {
  it('should auto-dismiss after duration', async () => {
    const TestComponent = () => {
      const { addToast } = useToast();
      return <button onClick={() => addToast({ 
        type: 'info', 
        message: 'Test',
        duration: 1000 
      })}>
        Show
      </button>;
    };

    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    screen.getByText('Show').click();
    expect(screen.getByText('Test')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.queryByText('Test')).not.toBeInTheDocument();
    }, { timeout: 1500 });
  });
});
```

**Test files to create:**
- `tests/components/Toast.test.tsx`
- `tests/components/LoadingStates.test.tsx`
- `tests/components/Pagination.test.tsx`
- `tests/components/ErrorBoundary.test.tsx`
- `tests/search/hooks/useSearchFilters.test.ts`

#### 17. Add Visual Regression Tests (2 days)
**Impact:** Medium | **Effort:** Medium | **Priority:** P2

```bash
npm install -D @percy/cli @percy/playwright
```

```typescript
// tests/e2e/visual.spec.ts
import percySnapshot from '@percy/playwright';

test('search page visual regression', async ({ page }) => {
  await page.goto('/search');
  await percySnapshot(page, 'Search Page - Empty');
  
  await page.fill('input[name="q"]', 'John 1:1');
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
  
  await percySnapshot(page, 'Search Page - With Results');
});
```

---

## Sprint 9-10: Performance & Polish (2 weeks)

**Goal:** Optimize performance and add finishing touches

### Week 9: Performance Optimization

#### 18. Implement List Virtualization (3 days)
**Impact:** High | **Effort:** Medium | **Priority:** P1

```bash
npm install @tanstack/react-virtual
```

**Target components:**
- Search results (100+ items)
- Verse mentions list
- Document list on upload page

```tsx
import { useVirtualizer } from '@tanstack/react-virtual';

export function VirtualizedResults({ items }) {
  const parentRef = useRef<HTMLDivElement>(null);
  
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 100,
    overscan: 5
  });

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map(virtualRow => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${virtualRow.start}px)`
            }}
          >
            <ResultCard item={items[virtualRow.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

#### 19. Add Dynamic Imports for Heavy Components (1 day)
**Impact:** Medium | **Effort:** Low | **Priority:** P2

```tsx
// app/verse/[osis]/page.tsx
import dynamic from 'next/dynamic';

const VerseGraph = dynamic(() => import('./VerseGraphSection'), {
  loading: () => <Skeleton height="400px" />,
  ssr: false // D3.js doesn't need SSR
});
```

**Target components:**
- `VerseGraphSection` (D3.js heavy)
- `GeoPanel` (map rendering)
- Any chart/visualization components

#### 20. Optimize Bundle with Tree Shaking (1 day)
**Impact:** Medium | **Effort:** Low | **Priority:** P2

Audit and optimize imports:
```tsx
// Before
import * as d3 from 'd3';

// After (tree-shakeable)
import { select, scaleLinear } from 'd3';
```

### Week 10: Final Polish

#### 21. Add Breadcrumb Navigation (2 days)
**Impact:** Medium | **Effort:** Medium | **Priority:** P2

```tsx
// app/components/Breadcrumbs.tsx
export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav aria-label="Breadcrumb" className="breadcrumbs">
      <ol>
        {items.map((item, index) => (
          <li key={item.href}>
            {index < items.length - 1 ? (
              <Link href={item.href}>{item.label}</Link>
            ) : (
              <span aria-current="page">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
```

Use on:
- `/verse/[osis]` page
- `/doc/[id]` page
- `/notebooks/[id]` page

#### 22. Implement Command Palette (Optional) (3 days)
**Impact:** High | **Effort:** High | **Priority:** P3

```bash
npm install cmdk
```

```tsx
// app/components/CommandPalette.tsx
import { Command } from 'cmdk';

export function CommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  return (
    <Command.Dialog open={open} onOpenChange={setOpen}>
      <Command.Input placeholder="Search or jump to..." />
      <Command.List>
        <Command.Group heading="Pages">
          <Command.Item onSelect={() => router.push('/search')}>
            Search
          </Command.Item>
          {/* ... */}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
```

#### 23. Run Final Lighthouse Audit (1 day)
**Impact:** High | **Effort:** Low | **Priority:** P1

**Target scores:**
- Performance: 90+
- Accessibility: 95+
- Best Practices: 100
- SEO: 100

**Common fixes:**
- Add meta descriptions
- Optimize image formats (WebP)
- Add `rel="noopener"` to external links
- Ensure proper `<title>` tags

---

## Progress Tracking Dashboard

### Key Metrics

```markdown
## Technical Debt Reduction

### Inline Styles
- [x] Week 1: 642 → 550 (-14%)
- [x] Week 2: 550 → 400 (-27%)
- [ ] Week 3: 400 → 200 (-50%)
- [ ] Week 4: 200 → 50 (-75%)
- [ ] Week 5: 50 → 0 (-100%) ✅

### Component Size
- [x] SearchPageClient: 1785 → 400 lines (-78%)
- [ ] UploadPage: 846 → 250 lines (-70%)
- [ ] CopilotPage: 837 → 350 lines (-58%)

### Test Coverage
- [x] E2E Tests: ✅ Good
- [ ] Unit Tests: 35% → 80%
- [ ] Visual Tests: 0% → 100%

### Accessibility
- [ ] Heading hierarchy: ✅ Fixed
- [ ] ARIA live regions: ✅ Added
- [ ] Axe violations: 12 → 0
- [ ] Keyboard nav: ✅ Perfect

### Performance
- [ ] Bundle size: -15%
- [ ] First Contentful Paint: < 1.5s
- [ ] Largest Contentful Paint: < 2.5s
- [ ] Time to Interactive: < 3.5s
```

---

## Resource Requirements

### Developer Time
- **Sprints 1-2:** 1 developer full-time
- **Sprints 3-4:** 1 developer full-time
- **Sprints 5-6:** 1 developer full-time
- **Sprints 7-8:** 1 developer + QA part-time
- **Sprints 9-10:** 1 developer full-time

**Total:** ~10 weeks (1 developer)

### External Dependencies
```json
{
  "new-dependencies": [
    "lucide-react",
    "@tanstack/react-virtual",
    "@axe-core/playwright",
    "@percy/playwright",
    "cmdk" // optional
  ]
}
```

### Budget Estimate
- Developer time: 400 hours @ $[rate]
- Axe/Percy licenses: ~$100/month
- Total: ~$[amount]

---

## Risk Mitigation

### Potential Blocages

1. **Refactoring breaks existing functionality**
   - **Mitigation:** Run full E2E suite after each component refactor
   - **Fallback:** Keep feature flags for gradual rollout

2. **Performance degradation during migration**
   - **Mitigation:** Monitor bundle size with each PR
   - **Fallback:** Use dynamic imports aggressively

3. **Accessibility regressions**
   - **Mitigation:** Automated axe tests in CI/CD
   - **Fallback:** Manual testing checklist

---

## Success Criteria

### Definition of Done
- [ ] 0 inline styles remaining
- [ ] All components < 600 lines
- [ ] 80%+ test coverage
- [ ] 0 critical axe violations
- [ ] Lighthouse score 90+ on all metrics
- [ ] Documentation updated
- [ ] Code reviewed and approved

### Sprint Acceptance Criteria
Each sprint must include:
- [ ] All tasks completed
- [ ] E2E tests passing
- [ ] No new accessibility violations
- [ ] Bundle size not increased
- [ ] PR reviewed and merged
- [ ] Documentation updated

---

## Communication Plan

### Weekly Updates
Send progress report every Friday:
```markdown
## Week [N] Progress Report

### Completed
- ✅ Task 1: [Details]
- ✅ Task 2: [Details]

### In Progress
- 🔄 Task 3: [50% complete]

### Blocked
- ⚠️ Task 4: [Blocker description]

### Next Week
- 📋 Task 5
- 📋 Task 6

### Metrics
- Inline styles: 642 → 450 (-30%)
- Test coverage: 35% → 42%
- Bundle size: 1.2MB → 1.15MB
```

---

## Appendix: Quick Reference

### Inline Style → Utility Class Mapping

```tsx
// Spacing
style={{ marginTop: "1rem" }}         → className="mt-2"
style={{ padding: "1rem" }}           → className="p-2"
style={{ gap: "0.5rem" }}             → className="gap-1"

// Layout
style={{ display: "flex", flexDirection: "column" }} → className="stack-md"
style={{ display: "flex", gap: "0.5rem" }}           → className="cluster-sm"
style={{ display: "grid", gridTemplateColumns: "..." }} → className="grid-2"

// Colors
style={{ color: "#64748b" }}          → className="text-muted"
style={{ background: "#6366f1" }}     → className="bg-accent"

// Typography
style={{ fontSize: "0.875rem" }}      → className="text-sm"
style={{ fontWeight: "600" }}         → className="font-semibold"

// Borders
style={{ borderRadius: "0.75rem" }}   → className="radius-sm"
style={{ border: "1px solid ..." }}   → className="border"
```

### Component Checklist

Before marking component refactor as complete:
- [ ] No inline styles
- [ ] Uses utility classes
- [ ] Proper TypeScript types
- [ ] Accessible (ARIA labels, semantic HTML)
- [ ] Responsive (mobile-first)
- [ ] Has loading state
- [ ] Has error handling
- [ ] Unit tests added
- [ ] Documentation updated

---

**END OF ACTION PLAN**

Next Steps:
1. Review with team
2. Assign sprints to developers
3. Create GitHub issues/tickets
4. Start Sprint 1!
