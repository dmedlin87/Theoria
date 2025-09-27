import { cookies } from "next/headers";

import {
  DEFAULT_MODE_ID,
  MODE_COOKIE_KEY,
  RESEARCH_MODES,
  ResearchMode,
  ResearchModeId,
  isResearchModeId,
} from "./mode-config";

export function getActiveMode(): ResearchMode {
  const cookieStore = cookies();
  const raw = cookieStore.get(MODE_COOKIE_KEY)?.value;
  const modeId: ResearchModeId = isResearchModeId(raw) ? raw : DEFAULT_MODE_ID;
  return RESEARCH_MODES[modeId];
}
