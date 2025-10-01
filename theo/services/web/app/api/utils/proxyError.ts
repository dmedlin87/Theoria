import { NextResponse } from "next/server";

import { TRACE_HEADER_NAMES } from "../trace";

type ProxyErrorOptions = {
  message: string;
  status?: number;
  error?: unknown;
  logContext?: string;
};

function generateTraceId(): string {
  const cryptoRef: typeof globalThis.crypto | undefined =
    typeof crypto !== "undefined" ? crypto : undefined;
  if (cryptoRef && typeof cryptoRef.randomUUID === "function") {
    try {
      return cryptoRef.randomUUID();
    } catch (error) {
      console.warn("Failed to generate trace ID via crypto.randomUUID", error);
    }
  }
  return `trace-${Date.now().toString(16)}-${Math.random()
    .toString(16)
    .slice(2, 10)}`;
}

export function createProxyErrorResponse({
  error,
  logContext,
  message,
  status = 503,
}: ProxyErrorOptions): NextResponse {
  const traceId = generateTraceId();
  const headers = new Headers();
  for (const header of TRACE_HEADER_NAMES) {
    if (header === "x-trace-id") {
      headers.set(header, traceId);
    }
  }

  const response = NextResponse.json(
    {
      message,
      traceId,
    },
    { status, headers },
  );

  if (error) {
    console.error(logContext ?? message, error);
  } else {
    console.error(logContext ?? message);
  }

  return response;
}
