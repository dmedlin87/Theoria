export type ErrorDetails = {
  message: string;
  traceId: string | null;
};

const MESSAGE_KEYS = ["detail", "message", "error", "title"] as const;
const TRACE_KEYS = ["debug_report_id", "trace_id", "traceId", "debugReportId"] as const;
const TRACE_HEADER_KEYS = [
  "x-debug-report-id",
  "debug-report-id",
  "x-trace-id",
  "trace-id",
  "x-request-id",
  "traceparent",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function pickFirstString(values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (trimmed) {
        return trimmed;
      }
    }
    if (isRecord(value)) {
      for (const nested of Object.values(value)) {
        if (typeof nested === "string" && nested.trim()) {
          return nested.trim();
        }
      }
    }
  }
  return null;
}

function extractTraceIdFromHeaders(headers: Headers): string | null {
  for (const key of TRACE_HEADER_KEYS) {
    const headerValue = headers.get(key);
    if (headerValue && headerValue.trim()) {
      if (key === "traceparent") {
        const traceFromParent = parseTraceparentHeader(headerValue);
        if (traceFromParent) {
          return traceFromParent;
        }
        continue;
      }
      return headerValue.trim();
    }
  }
  return null;
}

function parseTraceparentHeader(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parts = trimmed.split("-");
  if (parts.length < 4) {
    return null;
  }
  const traceId = parts[1]?.trim();
  if (typeof traceId === "string" && traceId.length === 32) {
    return traceId.toLowerCase();
  }
  return null;
}

export async function parseErrorResponse(
  response: Response,
  fallbackMessage: string,
): Promise<ErrorDetails> {
  let traceId = extractTraceIdFromHeaders(response.headers);
  let message = fallbackMessage;

  let bodyText: string | null = null;
  try {
    bodyText = await response.text();
  } catch {
    return { message, traceId };
  }

  const trimmed = bodyText.trim();
  if (!trimmed) {
    return { message, traceId };
  }

  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    const candidates = MESSAGE_KEYS.map((key) => parsed[key]);
    const messageCandidate = pickFirstString(candidates);
    if (messageCandidate) {
      message = messageCandidate;
    } else {
      message = trimmed;
    }

    const traceCandidate = pickFirstString(TRACE_KEYS.map((key) => parsed[key]));
    if (traceCandidate) {
      traceId = traceCandidate;
    }
  } catch {
    message = trimmed;
  }

  return { message, traceId };
}
