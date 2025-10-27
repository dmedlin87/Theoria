import { expect, test as base } from "@playwright/test";

const CONSOLE_FAILURE_TYPES = new Set<string>(["error", "warning"]);
const NETWORK_IDLE_TIMEOUT_MS = Number(
  process.env.PLAYWRIGHT_NETWORK_IDLE_TIMEOUT_MS ?? "15000"
);

const shouldFailConsoleMessage = (type: string): boolean =>
  CONSOLE_FAILURE_TYPES.has(type);

export const test = base.extend({});
export { expect };

test.beforeEach(async ({ page }, testInfo) => {
  let failureTriggered = false;
  let networkIdleTimer: NodeJS.Timeout | null = null;
  let activeRequests = 0;
  let sawAnyRequest = false;
  let lastRequestUrl: string | null = null;

  const failTest = (message: string): void => {
    if (failureTriggered) {
      return;
    }
    failureTriggered = true;
    clearNetworkIdleTimer();
    throw new Error(
      `E2E guard failure in "${testInfo.title}": ${message}`
    );
  };

  function clearNetworkIdleTimer(): void {
    if (networkIdleTimer) {
      clearTimeout(networkIdleTimer);
      networkIdleTimer = null;
    }
  }

  const scheduleNetworkIdleTimer = (): void => {
    if (!sawAnyRequest || activeRequests > 0) {
      return;
    }

    clearNetworkIdleTimer();
    networkIdleTimer = setTimeout(() => {
      failTest(
        `network remained idle for more than ${NETWORK_IDLE_TIMEOUT_MS}ms` +
          (lastRequestUrl ? ` after ${lastRequestUrl}` : "")
      );
    }, NETWORK_IDLE_TIMEOUT_MS);
  };

  page.on("console", (message) => {
    const type = message.type();
    if (!shouldFailConsoleMessage(type)) {
      return;
    }
    failTest(`console ${type}: ${message.text()}`);
  });

  page.on("pageerror", (error) => {
    failTest(`unhandled page error: ${error.message}`);
  });

  page.on("request", (request) => {
    sawAnyRequest = true;
    activeRequests += 1;
    lastRequestUrl = request.url();
    clearNetworkIdleTimer();
  });

  const handleRequestSettled = (): void => {
    activeRequests = Math.max(activeRequests - 1, 0);
    scheduleNetworkIdleTimer();
  };

  page.on("requestfinished", handleRequestSettled);

  page.on("requestfailed", (request) => {
    handleRequestSettled();
    const failure = request.failure();
    const failureText = failure?.errorText ? ` (${failure.errorText})` : "";
    failTest(
      `request failed: ${request.method()} ${request.url()}${failureText}`
    );
  });

  page.on("response", (response) => {
    const status = response.status();
    if (status < 400) {
      return;
    }
    failTest(
      `HTTP ${status} for ${response.request().method()} ${response.url()}`
    );
  });

  page.on("close", () => {
    clearNetworkIdleTimer();
  });

  scheduleNetworkIdleTimer();
});
