import { NextResponse } from "next/server";

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const discoveryId = params.id;

    // TODO: Call the actual FastAPI backend endpoint
    // const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    // const response = await fetch(`${backendUrl}/api/discoveries/${discoveryId}/view`, {
    //   method: "POST",
    //   headers: {
    //     "Authorization": `Bearer ${process.env.THEO_SEARCH_API_KEY}`,
    //   },
    // });

    console.log(`Marking discovery ${discoveryId} as viewed`);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error marking discovery as viewed:", error);
    return NextResponse.json(
      { error: "Failed to mark discovery as viewed" },
      { status: 500 }
    );
  }
}
