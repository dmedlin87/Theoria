import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardTraceHeaders } from "../../trace";
import { createProxyErrorResponse } from "../../utils/proxyError";
import { fetchWithTimeout } from "../../utils/fetchWithTimeout";

function buildAuthHeaders(): Headers {
  const headers = new Headers({ Accept: "application/json" });
  const apiKey = process.env.THEO_SEARCH_API_KEY?.trim();
  if (apiKey) {
    if (/^Bearer\s+/i.test(apiKey)) {
      headers.set("Authorization", apiKey);
    } else {
      headers.set("X-API-Key", apiKey);
    }
  }
  return headers;
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse> {
  const { id } = params;
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL(`/discoveries/${encodeURIComponent(id)}`, `${baseUrl}/api`);
  const headers = buildAuthHeaders();
  forwardTraceHeaders(request.headers, headers);

  try {
    const response = await fetchWithTimeout(target, {
      method: "DELETE",
      headers,
      cache: "no-store",
    });
    const body = await response.text();
    const proxyHeaders = new Headers();
    forwardTraceHeaders(response.headers, proxyHeaders);
    if (body) {
      proxyHeaders.set(
        "content-type",
        response.headers.get("content-type") ?? "application/json"
      );
    }
    return new NextResponse(body, {
      status: response.status,
      headers: proxyHeaders,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to dismiss discovery",
      message: "Unable to dismiss discovery. Please try again shortly.",
    });
  }
}
