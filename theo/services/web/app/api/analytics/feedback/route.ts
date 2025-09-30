import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardTraceHeaders } from "../../trace";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL("/analytics/feedback", baseUrl);
  const body = await request.text();
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
}
