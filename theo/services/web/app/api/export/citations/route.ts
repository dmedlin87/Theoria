import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardAuthHeaders } from "../../auth";
import { forwardTraceHeaders } from "../../trace";
import { createProxyErrorResponse } from "../../utils/proxyError";
import { fetchWithTimeout } from "../../utils/fetchWithTimeout";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const body = await request.text();
  
  const outboundHeaders = new Headers();
  forwardAuthHeaders(request.headers, outboundHeaders);
  forwardTraceHeaders(request.headers, outboundHeaders);
  outboundHeaders.set("content-type", "application/json");

  try {
    const response = await fetchWithTimeout(`${baseUrl}/export/citations`, {
      method: "POST",
      headers: outboundHeaders,
      body,
    });
    const responseBody = await response.text();
    const headers = new Headers();
    headers.set("content-type", response.headers.get("content-type") ?? "application/json");
    forwardTraceHeaders(response.headers, headers);
    
    // Forward content-disposition for downloads
    const contentDisposition = response.headers.get("content-disposition");
    if (contentDisposition) {
      headers.set("content-disposition", contentDisposition);
    }
    
    return new NextResponse(responseBody, {
      status: response.status,
      headers,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to proxy citation export request",
      message: "Citation export service is currently unavailable. Please try again later.",
      status: 502,
    });
  }
}
