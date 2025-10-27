import { getApiBaseUrl } from "../lib/api";
import type { ResearchFeatureFlags } from "./types";

export type ResearchFeaturesResult = {
  features: ResearchFeatureFlags | null;
  error: string | null;
};

function formatResponseError(response: Response, body: string | null): string {
  const status = response.status ? `${response.status}` : "";
  const statusText = response.statusText?.trim();
  const details = [status, statusText, body?.trim()].filter(Boolean).join(" ");
  return details ? `Unable to load research features: ${details}` : "Unable to load research features.";
}

export async function fetchResearchFeatures(): Promise<ResearchFeaturesResult> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  try {
    const response = await fetch(`${baseUrl}/features/discovery`, { cache: "no-store" });
    if (!response.ok) {
      const body = await response.text().catch(() => null);
      const message = formatResponseError(response, body);
      console.error("Failed to load discovery features", message);
      return { features: null, error: message };
    }
    const payload = (await response.json()) as unknown;
    if (payload && typeof payload === "object" && "features" in payload) {
      const { features } = payload as { features?: ResearchFeatureFlags | null };
      return { features: features ?? {}, error: null };
    }
    if (payload && typeof payload === "object") {
      return { features: payload as ResearchFeatureFlags, error: null };
    }
    return { features: {}, error: null };
  } catch (error) {
    const message =
      error instanceof Error && error.message
        ? `Unable to load research features: ${error.message}`
        : "Unable to load research features.";
    console.error("Failed to load discovery features", error);
    return { features: null, error: message };
  }
}
