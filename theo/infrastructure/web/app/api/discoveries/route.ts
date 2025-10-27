import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../lib/api";
import { forwardTraceHeaders } from "../trace";
import { createProxyErrorResponse } from "../utils/proxyError";
import { fetchWithTimeout } from "../utils/fetchWithTimeout";

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

function buildTargetUrl(request: NextRequest): URL {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL("/discoveries", `${baseUrl}/api`);
  request.nextUrl.searchParams.forEach((value, key) => {
    if (value != null && value !== "") {
      target.searchParams.set(key, value);
    }
  });
  return target;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const target = buildTargetUrl(request);
  const headers = buildAuthHeaders();
  forwardTraceHeaders(request.headers, headers);

  try {
    const response = await fetchWithTimeout(target, {
      headers,
      cache: "no-store",
    });
    const body = await response.text();
    const proxyHeaders = new Headers();
    proxyHeaders.set(
      "content-type",
      response.headers.get("content-type") ?? "application/json"
    );
    forwardTraceHeaders(response.headers, proxyHeaders);
    return new NextResponse(body, {
      status: response.status,
      headers: proxyHeaders,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to fetch discoveries",
      message: "Discoveries are currently unavailable. Please try again later.",
    });
  }
}
