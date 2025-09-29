"use client";

type TelemetryEventInput = {
  event: string;
  durationMs: number;
  workflow?: string;
  metadata?: Record<string, unknown>;
};

type TelemetryPayload = {
  events: Array<{
    event: string;
    duration_ms: number;
    workflow?: string;
    metadata?: Record<string, unknown>;
  }>;
  page?: string | null;
};

export async function emitTelemetry(
  events: TelemetryEventInput[],
  context?: { page?: string },
): Promise<void> {
  if (events.length === 0) {
    return;
  }
  const payload: TelemetryPayload = {
    events: events.map((event) => ({
      event: event.event,
      duration_ms: Math.max(0, event.durationMs),
      workflow: event.workflow,
      metadata: event.metadata,
    })),
    page: context?.page ?? undefined,
  };
  try {
    await fetch("/api/analytics/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.debug("Failed to emit telemetry", error);
    }
  }
}
