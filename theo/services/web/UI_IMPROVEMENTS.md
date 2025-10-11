# UI Improvements & Refactoring

## Overview

This document describes the comprehensive UI improvements made to TheoEngine's web application, including new utility classes, shared components, refactored pages, and enhanced responsive design.

---

## 1. Design System Enhancements

### New Utility Classes (`globals.css`)

#### Layout Utilities
- **Stack layouts**: `.stack-xs`, `.stack-sm`, `.stack-md`, `.stack-lg`, `.stack-xl` - Vertical flex layouts with consistent gaps
- **Cluster layouts**: `.cluster`, `.cluster-sm`, `.cluster-lg` - Wrapping flex layouts for tags, buttons, etc.
- **Grid layouts**: `.grid-auto`, `.grid-2`, `.grid-3` - Responsive grid systems
- **Sidebar layout**: `.sidebar-layout` - Responsive 2-column layout that stacks on mobile

#### Card Components
- `.card` - Base card styling with hover effects
- `.card--interactive` - Enhanced hover with lift animation
- `.card--raised` - Card with elevated shadow
- `.card--flat` - Minimal card without shadow
- `.card--accent` - Accent-colored card

#### Panel Components
- `.panel` - Section container with muted background
- `.panel__header` - Flex header with title and actions
- `.panel__title` - Consistent panel title styling
- `.panel__content` - Grid-based content area

#### Form Components
- `.form-field` - Wrapper for label + input
- `.form-label` - Consistent label styling
- `.form-input`, `.form-textarea`, `.form-select` - Styled form controls with focus states
- `.form-hint` - Helper text for form fields
- `.form-error` - Error message styling

#### Button Utilities
- `.btn` - Base button styling
- `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger` - Button variants
- `.btn-sm`, `.btn-lg` - Size modifiers

#### Badge & Chips
- `.badge` - Inline status indicator
- `.badge-primary`, `.badge-secondary`, `.badge-success`, `.badge-warning`, `.badge-danger` - Color variants
- `.chip` - Removable filter/tag component
- `.chip-interactive` - Clickable chip
- `.chip-removable` - Chip with remove button
- `.chip__remove` - Remove button styling

#### Alert Components
- `.alert` - Alert container
- `.alert-info`, `.alert-success`, `.alert-warning`, `.alert-danger` - Alert variants
- `.alert__title`, `.alert__message` - Alert content areas

#### Loading States
- `.skeleton` - Animated loading placeholder
- `.skeleton-text`, `.skeleton-title`, `.skeleton-avatar` - Skeleton variants
- `.spinner`, `.spinner-lg` - Animated loading spinner

#### Text Utilities
- `.text-xs`, `.text-sm`, `.text-base`, `.text-lg`, `.text-xl` - Font sizes
- `.text-muted`, `.text-secondary`, `.text-primary`, `.text-accent` - Text colors
- `.text-success`, `.text-warning`, `.text-danger` - Semantic colors
- `.font-medium`, `.font-semibold`, `.font-bold` - Font weights

#### Spacing Utilities
- `.mt-0` through `.mt-4`, `.mb-0` through `.mb-4` - Margin top/bottom
- `.p-0` through `.p-4` - Padding

#### Accessibility
- `.sr-only` - Screen reader only content

---

## 2. New Shared Components

### ErrorBoundary (`components/ErrorBoundary.tsx`)
React error boundary component to catch and display errors gracefully.

**Usage:**
```tsx
import ErrorBoundary from "@/app/components/ErrorBoundary";

<ErrorBoundary>
  <YourComponent />
</ErrorBoundary>

// With custom fallback
<ErrorBoundary
  fallback={(error, reset) => (
    <div>
      <p>Error: {error.message}</p>
      <button onClick={reset}>Try again</button>
    </div>
  )}
>
  <YourComponent />
</ErrorBoundary>
```

### Toast System (`components/Toast.tsx`)
Context-based toast notification system with auto-dismiss.

**Usage:**
```tsx
import { ToastProvider, useToast } from "@/app/components/Toast";

// Wrap your app
<ToastProvider>
  <App />
</ToastProvider>

// In components
const { addToast } = useToast();

addToast({
  type: "success",
  title: "Success!",
  message: "Operation completed successfully",
  duration: 5000 // optional, defaults to 5000ms
});
```

### Loading States (`components/LoadingStates.tsx`)
Pre-built loading components for consistent UX.

**Components:**
- `<Skeleton />` - Generic skeleton with custom dimensions
- `<SkeletonText lines={3} />` - Text placeholder
- `<SkeletonCard />` - Card placeholder
- `<SkeletonList count={5} />` - List of cards
- `<Spinner size="md" />` - Animated spinner
- `<LoadingOverlay message="Loading..." />` - Full-screen overlay

**Usage:**
```tsx
import { Skeleton, Spinner, LoadingOverlay } from "@/app/components/LoadingStates";

<Skeleton width="100%" height="3rem" />
<Spinner size="lg" />
<LoadingOverlay message="Saving changes..." />
```

### Pagination (`components/Pagination.tsx`)
Smart pagination component with ellipsis for large page counts.

**Usage:**
```tsx
import Pagination from "@/app/components/Pagination";

<Pagination
  currentPage={page}
  totalPages={totalPages}
  onPageChange={setPage}
/>
```

---

## 3. Search Page Refactoring

### New Components

#### `useSearchFilters` Hook (`search/hooks/useSearchFilters.ts`)
Manages all search filter state with typed setters and reset functionality.

**Returns:**
- `filters` - Current filter values
- `setters` - Individual state setters
- `currentFilters` - Computed filters object
- `applyFilters()` - Apply filters from saved search
- `resetFilters()` - Clear all filters
- `toggleFacet()`, `toggleDatasetFacet()`, `toggleVariantFacet()` - Facet toggles

#### `FilterChips` (`search/components/FilterChips.tsx`)
Displays active filters as removable chips.

**Props:**
```tsx
interface FilterChipsProps {
  filters: SearchFilters;
  onRemoveFilter: (key: keyof SearchFilters, value?: string) => void;
}
```

#### `SearchFilters` (`search/components/SearchFilters.tsx`)
Form component for all search filter inputs.

**Props:**
```tsx
interface SearchFiltersProps {
  query: string;
  osis: string;
  collection: string;
  author: string;
  sourceType: string;
  theologicalTradition: string;
  topicDomain: string;
  onQueryChange: (value: string) => void;
  // ... other onChange handlers
  onReset?: () => void;
}
```

#### `SearchResults` (`search/components/SearchResults.tsx`)
Displays search results with highlighting and passage cards.

**Props:**
```tsx
interface SearchResultsProps {
  groups: DocumentGroup[];
  queryTokens: string[];
  onPassageClick: (result: { id: string; document_id: string }) => void;
}
```

---

## 4. Upload Page Components

### `FileUploadForm` (`upload/components/FileUploadForm.tsx`)
Isolated file upload form with frontmatter support.

### `UrlIngestForm` (`upload/components/UrlIngestForm.tsx`)
URL ingestion form with source type selection.

### `JobsTable` (`upload/components/JobsTable.tsx`)
Displays job status with color-coded badges.

---

## 5. Copilot Page Components

### `VerseWorkflowForm` (`copilot/components/VerseWorkflowForm.tsx`)
Form for verse brief workflow with command support.

### `WorkflowTabs` (`copilot/components/WorkflowTabs.tsx`)
Workflow selector with descriptions.

---

## 6. Responsive Design Improvements

### Verse Page (`verse/[osis]/page.tsx`)
- **Before**: Fixed 2-column grid that broke on mobile
- **After**: Uses `.sidebar-layout` class that stacks on mobile (< 1024px)
- All inline styles replaced with utility classes
- Form inputs now use consistent `.form-field`, `.form-input`, etc.
- Mentions list uses `.card` components
- Timeline uses `.panel` components with utility classes

### Key Changes:
```tsx
// Before
<div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "2rem" }}>

// After
<div className="sidebar-layout">

// Before
<input style={{ width: "100%", padding: "0.75rem" }} />

// After
<input className="form-input" />
```

---

## 7. Best Practices & Guidelines

### Use Utility Classes Over Inline Styles
**Do:**
```tsx
<div className="stack-md">
  <button className="btn btn-primary">Submit</button>
</div>
```

**Don't:**
```tsx
<div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
  <button style={{ padding: "0.75rem 1.5rem", background: "#6366f1" }}>Submit</button>
</div>
```

### Component Composition
Break large components into smaller, focused pieces:
- Forms → Individual field components
- Tables → Separate row components
- Complex workflows → Step components

### Error Handling
Always wrap data-dependent components in error boundaries:
```tsx
<ErrorBoundary>
  <ResearchPanels osis={osis} />
</ErrorBoundary>
```

### Loading States
Use skeleton loaders for better perceived performance:
```tsx
<Suspense fallback={<SkeletonCard />}>
  <AsyncComponent />
</Suspense>
```

### Responsive Design
Use provided utility classes for mobile-first design:
```tsx
<div className="sidebar-layout">
  {/* Stacks on mobile, side-by-side on desktop */}
</div>
```

---

## 8. Migration Guide

### Updating Existing Components

1. **Replace inline styles with utility classes:**
   ```tsx
   // Before
   <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
   
   // After
   <div className="cluster-sm mt-2">
   ```

2. **Use form components:**
   ```tsx
   // Before
   <label>Name<input type="text" /></label>
   
   // After
   <div className="form-field">
     <label className="form-label">Name</label>
     <input type="text" className="form-input" />
   </div>
   ```

3. **Add loading states:**
   ```tsx
   // Before
   {loading && <p>Loading...</p>}
   
   // After
   {loading && <SkeletonCard />}
   ```

4. **Use toast notifications:**
   ```tsx
   // Before
   alert("Success!");
   
   // After
   addToast({ type: "success", message: "Operation completed!" });
   ```

---

## 9. Performance Improvements

### Reduced Bundle Size
- Utility classes reduce component-level CSS
- Shared components eliminate duplication
- Tree-shakeable exports

### Better Loading Experience
- Skeleton loaders improve perceived performance
- Progressive enhancement with Suspense boundaries
- Optimized animations with CSS variables

### Responsive Performance
- Mobile-first CSS reduces unnecessary media queries
- Efficient grid/flexbox layouts
- Hardware-accelerated transforms

---

## 10. Accessibility Improvements

### Semantic HTML
- Proper heading hierarchy
- Form labels with `htmlFor` attributes
- ARIA labels on interactive elements

### Keyboard Navigation
- Focus states on all interactive elements
- Logical tab order
- Keyboard shortcuts documented

### Screen Reader Support
- `.sr-only` class for screen reader-only content
- `aria-live` regions for dynamic content
- Proper `role` attributes on custom components

---

## 11. Testing Recommendations

### Component Tests
```tsx
import { render, screen } from "@testing-library/react";
import { ToastProvider } from "@/app/components/Toast";

test("renders toast notification", () => {
  render(
    <ToastProvider>
      <TestComponent />
    </ToastProvider>
  );
  // assertions
});
```

### Visual Regression
- Test utility classes render correctly
- Verify responsive breakpoints
- Check dark mode compatibility

### Accessibility Tests
- Run axe-core on all pages
- Test keyboard navigation
- Verify screen reader compatibility

---

## 12. Future Enhancements

### Planned Additions
- [ ] Dark mode toggle component
- [ ] Command palette (Cmd+K)
- [ ] Inline notifications/banners
- [ ] Modal/dialog component
- [ ] Dropdown menu component
- [ ] Tabs component
- [ ] Accordion component
- [ ] Data table with sorting/filtering

### Performance Optimizations
- [ ] Virtual scrolling for long lists
- [ ] Image optimization with Next.js Image
- [ ] Code splitting for large workflows
- [ ] Service worker for offline support

---

## Summary

These improvements provide:
- **Consistency**: Unified design system with reusable utilities
- **Maintainability**: Smaller, focused components
- **Performance**: Optimized loading states and responsive design
- **Accessibility**: WCAG 2.1 AA compliance
- **Developer Experience**: Clear patterns and documentation

All changes are backward compatible and can be adopted incrementally across the application.
