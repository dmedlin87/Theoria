import { NextResponse } from "next/server";

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const discoveryId = params.id;
    const body = await request.json();
    const { helpful } = body;

    // TODO: Call the actual FastAPI backend endpoint
    // const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    // const response = await fetch(`${backendUrl}/api/discoveries/${discoveryId}/feedback`, {
    //   method: "POST",
    //   headers: {
    //     "Authorization": `Bearer ${process.env.THEO_SEARCH_API_KEY}`,
    //     "Content-Type": "application/json",
    //   },
    //   body: JSON.stringify({ helpful }),
    // });

    console.log(`Recording feedback for discovery ${discoveryId}: ${helpful ? "helpful" : "not helpful"}`);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error submitting feedback:", error);
    return NextResponse.json(
      { error: "Failed to submit feedback" },
      { status: 500 }
    );
  }
}
