import { isResearchModeId, RESEARCH_MODES } from "../../app/mode-config";

describe("isResearchModeId", () => {
  it("returns false for inherited Object.prototype keys", () => {
    expect(isResearchModeId("toString")).toBe(false);
  });

  it.each(Object.keys(RESEARCH_MODES))(
    "returns true for valid research mode id '%s'",
    (modeId) => {
      expect(isResearchModeId(modeId)).toBe(true);
    },
  );
});
