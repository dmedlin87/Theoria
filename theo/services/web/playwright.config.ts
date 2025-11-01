import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: [
    ["github"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    traceDir: "playwright-artifacts/traces",
    screenshot: "only-on-failure",
    video: isCI ? "retain-on-failure" : "off",
  },
  outputDir: "playwright-artifacts/default",
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command:
        "uvicorn theo.infrastructure.api.app.bootstrap.app_factory:create_app --factory --host 127.0.0.1 --port 8000",
      cwd: "../../..",
      env: { PYTHONPATH: ".", DATABASE_URL: "sqlite:///./playwright.db" },
      port: 8000,
      reuseExistingServer: !isCI,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: "npm run dev",
      cwd: ".",
      env: {
        NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000",
        NEXT_DISABLE_TELEMETRY: "1",
        NEXT_TELEMETRY_DISABLED: "1",
        NEXT_DISABLE_UPDATE_CHECK: "1",
      },
      port: 3000,
      reuseExistingServer: !isCI,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
