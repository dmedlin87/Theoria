import { defineConfig } from "vitest/config";

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    include: ["tests/**/*.vitest.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["tests/vitest.setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage",
      enabled: true,
      thresholds: {
        global: {
          statements: 90,
          lines: 90,
          functions: 90,
          branches: 85,
        },
        each: {
          statements: 80,
          lines: 80,
          functions: 80,
          branches: 80,
        },
      },
      include: [
        "app/components/ConnectionStatusIndicator.tsx",
        "app/components/Toast.tsx",
        "app/search/components/SearchFilters.tsx",
        "app/search/components/SearchResults.tsx",
        "app/upload/components/FileUploadForm.tsx",
        "app/admin/digests/components/WatchlistTable.tsx",
        "app/chat/components/SessionControls.tsx",
      ],
      exclude: ["tests/**"],
    },
  },
});
