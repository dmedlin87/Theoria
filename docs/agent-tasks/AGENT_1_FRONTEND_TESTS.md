# Agent Task 1: Fix Frontend Test Failures

## Priority: CRITICAL
**Estimated Time:** 2-4 hours  
**Owner:** Agent 1  
**Working Directory:** `theo/services/web/`

## Objective
Fix 2 failing test suites in the frontend to enable coverage reporting.

## Current Status
```
Test Suites:  2 failed | 9 passed (11 total)
Tests:        4 failed | 38 passed (42 total)
```

## Files You Own (Exclusive)
- `theo/services/web/tests/components/Toast.vitest.tsx`
- Any files in `theo/services/web/tests/components/` directory

## Problem Description
The Toast component tests are failing with role selector issues. The test expects `role="alert"` but the actual component uses different ARIA roles.

## Tasks

### 1. Analyze the Toast Component
- Read: `theo/services/web/app/components/Toast.tsx` (or similar location)
- Understand the actual ARIA roles used
- Check Radix UI Toast documentation for correct roles

### 2. Fix Test Assertions
- Update: `theo/services/web/tests/components/Toast.vitest.tsx`
- Change role selectors to match actual implementation
- Ensure tests use correct testing-library queries

### 3. Run Tests
```bash
cd theo/services/web
npm run test:vitest
```

### 4. Generate Coverage Report
Once all tests pass:
```bash
npm run test:vitest
# Coverage report will be in: theo/services/web/coverage/
```

## Expected Output

### Success Criteria
- [ ] All test suites passing (11/11)
- [ ] All tests passing (42/42)
- [ ] Coverage report generated successfully
- [ ] Coverage HTML report viewable at `coverage/index.html`

### Deliverables
1. Fixed test file(s)
2. Coverage report generated
3. Summary of changes made

## Context Files to Read
- `theo/services/web/vitest.config.ts` - Test configuration
- `theo/services/web/tests/vitest.setup.ts` - Test setup
- `theo/services/web/package.json` - Test scripts

## Testing Strategy
1. Run specific failing test first
2. Identify exact assertion failures
3. Check component source for actual implementation
4. Update test to match reality (not the other way around)
5. Verify all Toast tests pass
6. Run full test suite

## Common Issues to Check
- ARIA roles: `alert` vs `status` vs `region`
- Async rendering: Need `waitFor` or `findBy` queries?
- Toast lifecycle: Mount/unmount timing
- Radix UI specific patterns

## No Conflicts With
- Agent 2: Working on `theo/services/api/app/core/`
- Agent 3: Working on `theo/services/api/app/mcp/`
- Agent 4: Working on `theo/services/api/app/ingest/`
- Agent 5: Working on `theo/services/api/app/retriever/`
- Agent 6: Working on `theo/services/api/app/ai/`

## Report Format
```markdown
# Agent 1 Report: Frontend Tests Fixed

## Changes Made
- File: tests/components/Toast.vitest.tsx
  - Changed: [specific changes]
  - Reason: [why]

## Test Results
- Before: 38/42 passing
- After: 42/42 passing ✅

## Coverage Generated
- Location: theo/services/web/coverage/
- Overall: [X]%
- Components: [X]%

## Time Taken
[X] hours
```
