import { NextResponse } from "next/server";

export async function DELETE(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const discoveryId = params.id;

    // TODO: Call the actual FastAPI backend endpoint
    // const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    // const response = await fetch(`${backendUrl}/api/discoveries/${discoveryId}`, {
    //   method: "DELETE",
    //   headers: {
    //     "Authorization": `Bearer ${process.env.THEO_SEARCH_API_KEY}`,
    //   },
    // });

    console.log(`Dismissing discovery ${discoveryId}`);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error dismissing discovery:", error);
    return NextResponse.json(
      { error: "Failed to dismiss discovery" },
      { status: 500 }
    );
  }
}
