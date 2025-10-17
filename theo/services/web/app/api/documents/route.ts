import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../lib/api";
import { forwardAuthHeaders } from "../auth";
import { forwardTraceHeaders } from "../trace";
import { createProxyErrorResponse } from "../utils/proxyError";
import { fetchWithTimeout } from "../utils/fetchWithTimeout";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const searchParams = request.nextUrl.searchParams;
  const queryString = searchParams.toString();
  const url = queryString ? `${baseUrl}/documents?${queryString}` : `${baseUrl}/documents`;
  
  const outboundHeaders = new Headers();
  forwardAuthHeaders(request.headers, outboundHeaders);
  forwardTraceHeaders(request.headers, outboundHeaders);

  try {
    const response = await fetchWithTimeout(url, {
      method: "GET",
      headers: outboundHeaders,
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
      logContext: "Failed to proxy documents request",
      message: "Documents service is currently unavailable. Please try again later.",
      status: 502,
    });
  }
}
