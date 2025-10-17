# Incomplete Logic and Features

This document lists portions of the dashboard implementation that currently rely on placeholder logic and therefore represent incomplete product behavior.

## Dashboard quick statistics

- **File:** `theo/services/web/app/dashboard/components/QuickStats.tsx`
- **Issue:** The `loadStats` effect currently resolves to hard-coded mock numbers after a delay instead of requesting data from the backend. The code comment explicitly marks this as a TODO to "Replace with real API calls", so production stats cannot surface until the API integration is implemented.

## Dashboard recent activity feed

- **File:** `theo/services/web/app/dashboard/components/RecentActivity.tsx`
- **Issue:** The `loadActivities` function seeds the activity list with mock entries and notes a TODO to replace the logic with a real API call (or persisted local data). As a result, the dashboard cannot show actual user activity yet.
