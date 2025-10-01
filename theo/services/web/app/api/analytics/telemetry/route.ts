import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardTraceHeaders } from "../../trace";
import { createProxyErrorResponse } from "../../utils/proxyError";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL("/analytics/telemetry", baseUrl);
  const body = await request.text();
  try {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body,
      cache: "no-store",
    });
    const payload = await response.text();
    const headers = new Headers();
    headers.set("content-type", response.headers.get("content-type") ?? "application/json");
    forwardTraceHeaders(response.headers, headers);
    return new NextResponse(payload, { status: response.status, headers });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to proxy analytics telemetry request",
      message: "Telemetry service is currently unavailable. Please try again later.",
    });
  }
}
