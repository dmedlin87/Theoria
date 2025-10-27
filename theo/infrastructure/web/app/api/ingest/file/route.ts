import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardAuthHeaders } from "../../auth";
import { forwardTraceHeaders } from "../../trace";
import { createProxyErrorResponse } from "../../utils/proxyError";
import { fetchWithTimeout } from "../../utils/fetchWithTimeout";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const formData = await request.formData();
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const outboundHeaders = new Headers();
  forwardAuthHeaders(request.headers, outboundHeaders);
  forwardTraceHeaders(request.headers, outboundHeaders);

  try {
    const response = await fetchWithTimeout(`${baseUrl}/ingest/file`, {
      method: "POST",
      headers: outboundHeaders,
      body: formData,
    });
    const body = await response.text();
    const headers = new Headers();
    headers.set("content-type", response.headers.get("content-type") ?? "application/json");
    forwardTraceHeaders(response.headers, headers);
    return new NextResponse(body, {
      status: response.status,
      headers,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to proxy file ingestion request",
      message: "File ingestion service is currently unavailable. Please try again later.",
      status: 502,
    });
  }
}
