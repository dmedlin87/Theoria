import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";
import { forwardTraceHeaders } from "../../trace";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  let payload: unknown;
  try {
    payload = await request.json();
  } catch (error) {
    return NextResponse.json(
      { detail: "Invalid request payload" },
      { status: 400 },
    );
  }

  try {
    const outboundHeaders = new Headers({ "Content-Type": "application/json" });
    forwardTraceHeaders(request.headers, outboundHeaders);
    const response = await fetch(`${baseUrl}/ingest/simple`, {
      method: "POST",
      headers: outboundHeaders,
      body: JSON.stringify(payload),
    });

    const headers = new Headers();
    headers.set(
      "content-type",
      response.headers.get("content-type") ?? "application/x-ndjson",
    );
    forwardTraceHeaders(response.headers, headers);

    return new NextResponse(response.body, {
      status: response.status,
      headers,
    });
  } catch (error) {
    console.error("Failed to proxy simple ingest request", error);
    return NextResponse.json(
      {
        detail:
          "Unable to reach the ingestion API. Please check that the API service is running and reachable.",
      },
      { status: 502 },
    );
  }
}
