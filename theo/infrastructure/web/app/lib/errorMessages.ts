import { NetworkError, TheoApiError } from "./api-client";

export type ErrorFeature = "chat" | "search" | "upload";

export type ErrorInterpretationCategory =
  | "auth"
  | "not_found"
  | "server"
  | "network"
  | "unknown";

export type InterpretedApiError = {
  message: string;
  traceId: string | null;
  retryLabel?: string;
  helpLink?: string;
  helpLabel?: string;
  category: ErrorInterpretationCategory;
  status?: number | null;
};

export type InterpretApiErrorOptions = {
  feature: ErrorFeature;
  fallbackMessage?: string;
  status?: number | null;
  traceId?: string | null;
};

const RETRY_LABELS: Record<ErrorFeature, string> = {
  chat: "Retry question",
  search: "Retry search",
  upload: "Retry upload",
};

const SETTINGS_PATH = "/admin/settings";
const STATUS_PAGE_URL = "https://status.theo.ai/";
const CONNECTIVITY_GUIDE_URL = "https://docs.theo.ai/troubleshooting/connectivity";

export function interpretApiError(
  error: unknown,
  options: InterpretApiErrorOptions,
): InterpretedApiError {
  const { feature, fallbackMessage, status: explicitStatus, traceId: explicitTraceId } = options;

  let status = explicitStatus ?? null;
  let traceId = explicitTraceId ?? null;
  let message = fallbackMessage ?? "Something went wrong.";
  let category: ErrorInterpretationCategory = "unknown";
  let helpLink: string | undefined;
  let helpLabel: string | undefined;

  const defaultRetryLabel = RETRY_LABELS[feature] ?? "Retry";
  let retryLabel: string | undefined = defaultRetryLabel;

  if (error instanceof TheoApiError) {
    status = error.status;
    if (typeof error.message === "string" && error.message.trim()) {
      message = error.message.trim();
    }
  } else if (error instanceof NetworkError) {
    category = "network";
    message =
      "Theo couldn’t reach the API service. Confirm the server is reachable and try again.";
  } else if (error instanceof Error && typeof error.message === "string" && error.message.trim()) {
    message = error.message.trim();
  } else if (typeof error === "string" && error.trim()) {
    message = error.trim();
  }

  if (!traceId && error && typeof error === "object" && "traceId" in error) {
    const candidate = (error as { traceId?: string | null }).traceId;
    if (typeof candidate === "string" && candidate.trim()) {
      traceId = candidate.trim();
    }
  }

  const isFetchError =
    error instanceof NetworkError ||
    (error instanceof TypeError && /fetch/i.test(error.message ?? ""));

  if (isFetchError || status === 0) {
    category = "network";
    message =
      "Theo couldn’t reach the API service. Confirm the server is reachable and try again.";
    helpLink = CONNECTIVITY_GUIDE_URL;
    helpLabel = "View connectivity guide";
  } else if (status === 401 || status === 403) {
    category = "auth";
    message =
      "Theo couldn’t authenticate with the API. Add a valid API key in Settings, then try again.";
    helpLink = SETTINGS_PATH;
    helpLabel = "Open Settings";
  } else if (status === 404) {
    category = "not_found";
    message = "We couldn’t find that resource. Verify the identifier or try refreshing the data.";
  } else if (typeof status === "number" && status >= 500) {
    category = "server";
    message = "Theo’s services are having trouble responding. Please retry in a moment.";
    helpLink = STATUS_PAGE_URL;
    helpLabel = "Check system status";
  }

  return {
    message,
    traceId,
    retryLabel,
    helpLink,
    helpLabel,
    category,
    status,
  };
}
