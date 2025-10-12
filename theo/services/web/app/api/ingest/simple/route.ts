import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardTraceHeaders } from "../../trace";
import { createProxyErrorResponse } from "../../utils/proxyError";
import { fetchWithTimeout } from "../../utils/fetchWithTimeout";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  let payload: unknown;
  try {
    payload = await request.json();
  } catch (error) {
    return NextResponse.json(
      { detail: "Invalid request payload" },
      { status: 400 },
    );
  }

  try {
    const outboundHeaders = new Headers({ "Content-Type": "application/json" });
    forwardTraceHeaders(request.headers, outboundHeaders);
    const response = await fetchWithTimeout(`${baseUrl}/ingest/simple`, {
      method: "POST",
      headers: outboundHeaders,
      body: JSON.stringify(payload),
    });

    const headers = new Headers();
    headers.set(
      "content-type",
      response.headers.get("content-type") ?? "application/x-ndjson",
    );
    forwardTraceHeaders(response.headers, headers);

    return new NextResponse(response.body, {
      status: response.status,
      headers,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to proxy simple ingest request",
      message: "Simple ingestion service is currently unavailable. Please try again later.",
      status: 502,
    });
  }
}
