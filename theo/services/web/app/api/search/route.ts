import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../lib/api";

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
  const response = await fetch(target, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
    },
  });
}
