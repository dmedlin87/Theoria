import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardTraceHeaders } from "../../trace";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const formData = await request.formData();
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");

  try {
    const response = await fetch(`${baseUrl}/ingest/file`, {
      method: "POST",
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
    console.error("Failed to proxy file ingestion request", error);
    return NextResponse.json(
      {
        detail: "Unable to reach the ingestion API. Please check that the API service is running and reachable.",
      },
      { status: 502 },
    );
  }
}
