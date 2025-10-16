import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../../lib/api";
import { forwardTraceHeaders } from "../../../trace";
import { createProxyErrorResponse } from "../../../utils/proxyError";
import { fetchWithTimeout } from "../../../utils/fetchWithTimeout";

function buildAuthHeaders(request: NextRequest): Headers {
  const headers = new Headers({ Accept: "application/json" });
  const apiKey = process.env.THEO_SEARCH_API_KEY?.trim();
  if (apiKey) {
    if (/^Bearer\s+/i.test(apiKey)) {
      headers.set("Authorization", apiKey);
    } else {
      headers.set("X-API-Key", apiKey);
    }
  }
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  return headers;
}

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse> {
  const { id } = params;
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL(
    `/discoveries/${encodeURIComponent(id)}/feedback`,
    `${baseUrl}/api`
  );
  const headers = buildAuthHeaders(request);
  forwardTraceHeaders(request.headers, headers);

  let body: string;
  try {
    body = await request.text();
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to read feedback payload",
      message: "Unable to submit feedback at this time.",
    });
  }

  try {
    const response = await fetchWithTimeout(target, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
    });
    const responseBody = await response.text();
    const proxyHeaders = new Headers();
    forwardTraceHeaders(response.headers, proxyHeaders);
    if (responseBody) {
      proxyHeaders.set(
        "content-type",
        response.headers.get("content-type") ?? "application/json"
      );
    }
    return new NextResponse(responseBody, {
      status: response.status,
      headers: proxyHeaders,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to submit discovery feedback",
      message: "Unable to submit feedback at this time.",
    });
  }
}
