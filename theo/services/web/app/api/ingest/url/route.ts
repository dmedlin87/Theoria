import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardTraceHeaders } from "../../trace";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = await request.json();
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  try {
    const response = await fetch(`${baseUrl}/ingest/url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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
    console.error("Failed to proxy URL ingestion request", error);
    return NextResponse.json(
      {
        detail: "Unable to reach the ingestion API. Please check that the API service is running and reachable.",
      },
      { status: 502 },
    );
  }
}
