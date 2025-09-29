import { getApiBaseUrl } from "../lib/api";
import type { ResearchFeatureFlags } from "./types";

export async function fetchResearchFeatures(): Promise<ResearchFeatureFlags> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  try {
    const response = await fetch(`${baseUrl}/features/discovery`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const payload = (await response.json()) as unknown;
    if (payload && typeof payload === "object" && "features" in payload) {
      const { features } = payload as { features?: ResearchFeatureFlags | null };
      return features ?? {};
    }
    if (payload && typeof payload === "object") {
      return payload as ResearchFeatureFlags;
    }
    return {};
  } catch (error) {
    console.error("Failed to load discovery features", error);
    return {};
  }
}
