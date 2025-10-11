import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../lib/api";
import { forwardTraceHeaders } from "../trace";
import { createProxyErrorResponse } from "../utils/proxyError";

function buildTargetUrl(request: NextRequest): URL {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL("/search", baseUrl);
  request.nextUrl.searchParams.forEach((value, key) => {
    if (value) {
      target.searchParams.append(key, value);
    }
  });
  return target;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const target = buildTargetUrl(request);
  const apiKey = process.env.THEO_SEARCH_API_KEY?.trim();
  const requestHeaders = new Headers({ Accept: "application/json" });
  if (apiKey) {
    if (/^Bearer\s+/i.test(apiKey)) {
      requestHeaders.set("Authorization", apiKey);
    } else {
      requestHeaders.set("X-API-Key", apiKey);
    }
  }
  forwardTraceHeaders(request.headers, requestHeaders);
  try {
    const response = await fetch(target, {
      headers: requestHeaders,
      cache: "no-store",
    });
    const body = await response.text();
    const headers = new Headers();
    headers.set("content-type", response.headers.get("content-type") ?? "application/json");
    const reranker = response.headers.get("x-reranker");
    if (reranker) {
      headers.set("x-reranker", reranker);
    }
    forwardTraceHeaders(response.headers, headers);
    return new NextResponse(body, {
      status: response.status,
      headers,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to proxy search request",
      message: "Search service is currently unavailable. Please try again later.",
    });
  }
}
