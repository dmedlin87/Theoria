import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../lib/api";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const formData = await request.formData();
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/ingest/file`, {
    method: "POST",
    body: formData,
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
    },
  });
}
